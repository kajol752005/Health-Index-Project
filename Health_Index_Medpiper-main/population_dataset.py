import psycopg2
import pandas as pd

# Database connection details
conn = psycopg2.connect(
    dbname='medpiperdatabase',
    user='postgres',
    password='POSTSQLkashi@0025',
    host='localhost',
    port='5432'
)

cursor = conn.cursor()

# Create the table with the specified columns
cursor.execute('''
CREATE TABLE IF NOT EXISTS PopulationData (
    id SERIAL PRIMARY KEY,
    City VARCHAR(255),
    Population INTEGER,
    Common_Health_Diseases TEXT,
    Recommended_Health_Checkups TEXT
)
''')

# Load the CSV file
df = pd.read_csv('indian_cities_health_data.csv')

# Insert the data into the table
for row in df.itertuples(index=False):
    cursor.execute(
        '''
        INSERT INTO PopulationData (City, Population, Common_Health_Diseases, Recommended_Health_Checkups)
        VALUES (%s, %s, %s, %s)
        ''',
        (row.City, row.Population, row.Common_Health_Diseases, row.Recommended_Health_Checkups)
    )

# Commit the transaction and close the connection
conn.commit()
cursor.close()
conn.close()
