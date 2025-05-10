from neo4j import GraphDatabase

NEO4J_URI = "http://localhost:7474"
NEO4J_URI = "neo4j+s://9b2392e0.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "md9_IcJYXDjAN70Tq_XWyzZBvwel4q35zVPeCJYb_mM"

def connect_to_neo4j():
    # Connect to Neo4j database
    driver = neo4j.GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_URI, NEO4J_PASSWORD))
    return driver