# import psycopg2
# import pandas as pd

# # Database connection details
# conn = psycopg2.connect(
#         dbname='medpiperdatabase',
#         user='postgres',
#         password='POSTSQLkashi@0025',
#         host='localhost',
#         port='5432'
#     )

# cursor = conn.cursor()

# cursor.execute( '''
# CREATE TABLE IF NOT EXISTS airquality (
#     id SERIAL PRIMARY KEY,
#     AQI TEXT,
#     Category VARCHAR(255),
#     Diseases TEXT,
#     Health_Checkup TEXT
# )
# ''')

# df = pd.read_csv('AQI_Dataset.csv')

# # Insert the data into the table
# for row in df.itertuples(index=False):
#     cursor.execute(
#         '''
#         INSERT INTO airquality (AQI, Category, Diseases, Health_Checkup)
#         VALUES (%s, %s, %s, %s)
#         ''',
#         row
#     )

# # Commit the transaction and close the connection
# conn.commit()
# cursor.close()
# conn.close()

import psycopg2
import pandas as pd

# Database connection details
try:
    conn = psycopg2.connect(
        dbname='neondb',
        user='neondb_owner',
        password='EG0uyDzK5RZH',
        host='ep-twilight-surf-a5ehkaal.us-east-2.aws.neon.tech',
        port='5432',
        sslmode='require')
except Exception as e:
    print(f"Error connecting to the database: {e}")
    exit(1)

try:
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS airquality (
        id SERIAL PRIMARY KEY,
        AQI TEXT,
        Category VARCHAR(255),
        Diseases TEXT,
        Health_Checkup TEXT
    )
    ''')

    df = pd.read_csv('AQI_Dataset.csv')

    # Insert the data into the table
    for row in df.itertuples(index=False):
        cursor.execute(
            '''
            INSERT INTO airquality (AQI, Category, Diseases, Health_Checkup)
            VALUES (%s, %s, %s, %s)
            ''', (row.AQI, row.Category, row.Diseases, row.Health_Checkup))

    # Commit the transaction and close the connection
    conn.commit()
    cursor.close()
    conn.close()
    print("Data inserted successfully")

except Exception as e:
    print(f"Error during database operation: {e}")
    if conn:
        conn.rollback()
    exit(1)
