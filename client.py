from typing import Dict
from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from .models import AeomAction, AeomObservation, AeomState


class AeomEnv(EnvClient[AeomAction, AeomObservation, AeomState]):

    def _step_payload(self, action: AeomAction) -> Dict:
        return action.model_dump(exclude_none=True)

    def _parse_result(self, payload: Dict) -> StepResult[AeomObservation]:
        obs_data = payload.get("observation", {})
        obs = AeomObservation(
            ticket_status=obs_data.get("ticket_status", "open"),
            customer_reply=obs_data.get("customer_reply"),
            db_result=obs_data.get("db_result"),
            error_log=obs_data.get("error_log"),
            steps_taken=obs_data.get("steps_taken", 0),
            final_score=obs_data.get("final_score"),
            policy_snapshot=obs_data.get("policy_snapshot", {}),
            done=payload.get("done", False),
            reward=payload.get("reward", 0.0),
        )
        return StepResult(
            observation=obs,
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> AeomState:
        return AeomState(**payload)
