## 14/08/26

- Add dlt
- Add CI
- Improve devEx (using ruff (lint and format) and ty (typing))
- update ingestion/
    - remove stations ingestion
- remove grafana (in order to replace it by pydantic logfire)

## 15/08/26
- update evaluation/
- mettre dlt dans le diagramme
- switch from openai lib to pydanticAi that is more clean
- add logfire
- clean and updates pyproject

## 16/08/26
- lors de la génération du ground_truth_dataste
  - attention au biais de représentation uniforme
    - certains sujets méritent (10 questions -> complexes alors que d'autres triviales ne mérient que 1 ou 2). Donc le dataset n'est pas représentatif de la distribution réelle des questions
  - biais de l'instruction llm
    - force le llm à générer 5 questions donc potentiellement 2 très bonnes et 3 pas intéressantes
    


TODO:
- [ x ] utiliser un autre llm pour le judge
- ajouter dans la CI/CD les étapes d'évaluation du modèle obligatoirement !
- CI/CD
- Ajouter un readme pour les correcteurs
- Voir si je peux déployer l'app gratuitement cloud side sur une stack 
  - qdrant (dbvector)
  - pydantic logfire (monitoring) 
  - pydantic instance (agent API) 
  - streamlit (UI)

BONUS (next steps):
- pour l'agent llm intent/formater -> utiliser un modèle plus petit pour gagner en rapidité + coût
- Fonctionnalité query db pour un utilisateur afin d'avoir des stats velov
    - importer tout l'historique velov dans une bdd postgres+postgis 
    - creer un function_call (text_to_sql)
        - la question de l'user est transformé en requete et on l'exécute