from openenv.core.env_server.http_server import create_app

try:
    from ..models import AeomAction, AeomObservation
    from .aeom_env_environment import AeomEnvironment
except (ModuleNotFoundError, ImportError):
    from models import AeomAction, AeomObservation
    from server.aeom_env_environment import AeomEnvironment

app = create_app(
    AeomEnvironment,
    AeomAction,
    AeomObservation,
    env_name="aeom_env",
    max_concurrent_envs=4,
)


def main(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
