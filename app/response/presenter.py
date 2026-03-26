from app.models import ExecutionResult


class ResponsePresenter:
    def show(self, result: ExecutionResult):
        if result.success:
            print(f"[OK] {result.message}")
        else:
            print(f"[ERROR] {result.message}")