from sqlalchemy.orm import declarative_base

# Declarative base decoupled from runtime engine and connection pool
Base = declarative_base()

