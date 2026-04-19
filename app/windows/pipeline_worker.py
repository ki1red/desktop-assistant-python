def run_pipeline_once():
    from app.assistant_pipeline import AssistantPipeline

    pipeline = AssistantPipeline()
    pipeline.run_once()