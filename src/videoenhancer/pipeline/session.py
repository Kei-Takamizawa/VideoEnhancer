"""Model lifetime owned by one isolated part worker."""

from videoenhancer.pipeline.stages import Stage


class PipelineSession:
    def __init__(self) -> None:
        self.stages: list[Stage] | None = None
        self.verified = False

    def close(self) -> None:
        stages, self.stages = self.stages, None
        self.verified = False
        for stage in stages or []:
            stage.teardown()
