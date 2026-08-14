def run_all() -> None:
    from evaluation.retrieval_eval import main as retrieval
    from evaluation.llm_eval import main as llm

    retrieval()
    llm()
