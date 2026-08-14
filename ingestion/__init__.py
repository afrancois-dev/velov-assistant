def run_all() -> None:
    from ingestion.faq_pipeline import run as faq
    from ingestion.stations_pipeline import run as stations

    faq()
    stations()
