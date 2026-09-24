"""Run on the host: pip install 'neo4j>=5.26,<6', then python check_connection.py."""
import os
from getpass import getpass

from neo4j import GraphDatabase

uri = os.getenv("NEO4J_LOCAL_URI", "bolt://localhost:7687")
password = getpass("Mot de passe Neo4j : ")
with GraphDatabase.driver(uri, auth=("neo4j", password)) as driver:
    driver.verify_connectivity()
    records, _, _ = driver.execute_query("RETURN 1 AS ok", database_="neo4j")
    print(f"Connexion réussie : {records[0]['ok']}")
