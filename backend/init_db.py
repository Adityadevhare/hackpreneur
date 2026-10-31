
from database import Base, engine
import models

# Create all tables defined in models.py
Base.metadata.create_all(bind=engine)

print("HACKPRENEUR database initialized successfully!")
