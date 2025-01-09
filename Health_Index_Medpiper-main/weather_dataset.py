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
CREATE TABLE IF NOT EXISTS weatherdisease (
    id SERIAL PRIMARY KEY,
    range numrange NOT NULL,
    category VARCHAR(255) NOT NULL,
    Diseases_Caused TEXT,
    Recommended_Health_Checkup TEXT
)
''')

# Load the CSV file
df = pd.read_csv('weather_diseases.csv')  # Adjust the file path if necessary

# Insert the data into the table
for row in df.itertuples(index=False):
    cursor.execute(
        '''
        INSERT INTO weatherdisease (range, category, Diseases_Caused, Recommended_Health_Checkup)
        VALUES (%s::numrange, %s, %s, %s)
        ''',
        (row.range, row.category,  row.Diseases_Caused, row.Recommended_Health_Checkup)
    )

# Commit the transaction and close the connection
conn.commit()
cursor.close()
conn.close()
