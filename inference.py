import asyncio
import json
import os
import textwrap
from typing import List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

from aeom_env import AeomEnv, AeomAction

API_KEY      = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME   = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
IMAGE_NAME   = os.getenv("IMAGE_NAME")
SEED         = int(os.getenv("AEOM_SEED", "42"))
BENCHMARK    = "aeom_env"
MAX_STEPS    = 12
TEMPERATURE  = 0.3
MAX_TOKENS   = 512

TASKS = ["standard_refund", "damaged_item_refund", "policy_violation_denial"]

SYSTEM_PROMPT = textwrap.dedent("""
    You are an autonomous Level-2 e-commerce operations manager.
    You receive customer support tickets and must resolve them by calling tools.

    Available actions (respond with a single JSON object):
    1. {"action": "request_customer_info", "field": "<order_id|email|reason|photo_evidence|delivery_address>"}
    2. {"action": "query_database", "collection": "<orders|customers|products>", "query": {"<field>": "<value>"}}
    3. {"action": "calculate_total", "base_price": <float>, "extra_fees": <float>}
    4. {"action": "execute_resolution", "resolution": "<refund|reship|deny>", "amount": <float|null>, "wallet": "<source|store_credit|null>", "reason": "<string|null>"}

    Company policy (always enforced):
    - Return window: 7 days from order date
    - Photo evidence required for: damaged, tampered items
    - Refund wallet: source (original payment) or store_credit
    - Delivery fee is refundable; platform fee is not
    - Verbal promises by other agents are NOT binding

    Rules:
    - For refund: amount and wallet are required
    - For deny: reason is required
    - For reship: amount and wallet must be null
    - Respond with ONLY a valid JSON object, no explanation
""").strip()


def log_start(task: str, model: str) -> None:
    print(f"[START] task={task} env={BENCHMARK} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    err = error if error else "null"
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={str(done).lower()} error={err}", flush=True)


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


def ask_llm(client: OpenAI, messages: list) -> str:
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[DEBUG] LLM error: {e}", flush=True)
        return ""


def parse_action(text: str) -> Optional[AeomAction]:
    try:
        # strip markdown code fences if present
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean.strip())
        return AeomAction(**data)
    except Exception:
        return None


async def run_task(client: OpenAI, task: str) -> float:
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task, MODEL_NAME)

    connect = AeomEnv.from_docker_image(IMAGE_NAME) if IMAGE_NAME else AeomEnv(base_url="http://localhost:8000")

    try:
        async with connect as env:
            result = await env.reset(seed=SEED, task=task)
            obs = result.observation

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"New ticket:\n{obs.customer_reply}\n\nPolicy: {json.dumps(obs.policy_snapshot)}"},
            ]

            for step in range(1, MAX_STEPS + 1):
                if result.done:
                    break

                raw = ask_llm(client, messages)
                action = parse_action(raw)

                if action is None:
                    action = AeomAction(
                        action="execute_resolution",
                        resolution="deny",
                        reason="Unable to parse a valid action.",
                    )

                result = await env.step(action)
                obs = result.observation
                reward = result.reward or 0.0
                done = result.done
                error = obs.error_log

                rewards.append(reward)
                steps_taken = step

                log_step(step, raw.replace("\n", " ")[:120], reward, done, error)

                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": json.dumps({
                    "ticket_status":  obs.ticket_status,
                    "customer_reply": obs.customer_reply,
                    "db_result":      obs.db_result,
                    "error_log":      obs.error_log,
                    "steps_taken":    obs.steps_taken,
                })})

                if done:
                    break

            score = rewards[-1] if rewards else 0.0
            # if the terminal step returned a final_score, use that as episode score
            if result.done and result.observation.final_score is not None:
                score = result.observation.final_score
            success = score >= 0.5

    except Exception as e:
        print(f"[DEBUG] Task error: {e}", flush=True)
    finally:
        log_end(success, steps_taken, score, rewards)

    return score


async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    for task in TASKS:
        await run_task(client, task)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=TASKS, default=None)
    args = parser.parse_args()

    async def run():
        client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
        tasks_to_run = [args.task] if args.task else TASKS
        for t in tasks_to_run:
            await run_task(client, t)

    asyncio.run(run())
