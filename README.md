# velov-assistant
An AI assistant for Lyon's self-service bike network with:
- real-time station availability and nearby bike location (function call)
- service FAQ answers powered by RAG

# Project

## Problem description
Tourist or new comers to the city of Lyon needs information about how the velov works. Those information are provided on the FAQ of the velov website;
 however, it can be tedious to consult the website. Moreover, the assistant provide a real time availabily checker for bike station.

- An user could ask question such as which is the nearest station available nearby in Part-Dieu? 
- Can I book several bikes? 


## Retrieval flow (knowledge base + llm)

## Retrieval evaluation (multiple retrieval approaches are evaluated and the best one is used) e.g text search + vector search

## LLM evaluation (multiple approaches evaluated and the best one is used)

## Interface (api or visual interface such as grafana)


## Ingestion pipeline (automated ingestion i.e airflow, kestra, dlt, bruin)

## Monitoring (i.e User feedback is collected and there's a dashboard with at least 5 charts)

## Containerization (everything in docker-compose)


## Reproducibility
- Instructions are clear, the dataset is accessible, it's easy to run the code, and it works. The versions for all dependencies are specified.


## Bonus
- Best practices
 - Hybrid search: combining both text and vector search (at least evaluating it) (1 point)
 - Document re-ranking (1 point)
 - User query rewriting (1 point)
- Bonus points (not covered in the course)
 - Deployment to the cloud (2 points)
 - Up to 3 extra bonus points if you want to award for something extra (write in feedback for what)