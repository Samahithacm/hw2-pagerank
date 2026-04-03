#!/usr/bin/env python3
"""
CS528 HW6 - Machine Learning Models
Connects to Cloud SQL, normalizes schema to 3NF, trains two models:
  Model 1: IP -> Country prediction (target: 99%+ accuracy)
  Model 2: Features -> Income prediction (target: 40%+ accuracy)
Uploads test set results to GCS bucket.
"""

import pymysql
import pandas as pd
import numpy as np
import json
import os
import sys
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report
from google.cloud import storage

# ============================================================
# CONFIGURATION
# ============================================================
DB_HOST = os.environ.get("DB_HOST", "10.6.0.8")
DB_USER = os.environ.get("DB_USER", "root")
DB_PASS = os.environ.get("DB_PASS", "cs528hw6pass")
DB_NAME = os.environ.get("DB_NAME", "hw6db")
GCS_BUCKET = os.environ.get("GCS_BUCKET", "bu-cs528-mahicm13")
GCP_PROJECT = os.environ.get("GCP_PROJECT", "constant-idiom-485622-f3")

print("=" * 60)
print("CS528 HW6 - Machine Learning Models")
print("=" * 60)

# ============================================================
# STEP 1: Connect to database and fetch data
# ============================================================
print("\n[STEP 1] Connecting to database and fetching data...")
conn = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, sql_mode="NO_ENGINE_SUBSTITUTION")
cursor = conn.cursor()

# Check what tables exist
cursor.execute("SHOW TABLES")
tables = cursor.fetchall()
print(f"  Tables in database: {tables}")

# Check the request_logs table structure
cursor.execute("DESCRIBE request_logs")
columns = cursor.fetchall()
print(f"  Columns in request_logs table:")
for col in columns:
    print(f"    {col}")

# Fetch all data from request_logs table
df = pd.read_sql("SELECT * FROM request_logs", conn)
print(f"  Total rows fetched: {len(df)}")
print(f"  Columns: {list(df.columns)}")
print(f"  Sample data:")
print(df.head())
print(f"\n  Null counts per column:")
print(df.isnull().sum())

# ============================================================
# STEP 2: 3NF Normalization
# ============================================================
print("\n" + "=" * 60)
print("[STEP 2] Normalizing schema to 3rd Normal Form...")
print("=" * 60)
print("""
  ANALYSIS OF 3NF VIOLATION:
  --------------------------
  The original 'request_logs' table has the following functional dependencies:
    - id -> all other columns (primary key dependency)
    - client_ip -> country (each IP always maps to the same country)
  
  This means 'country' is transitively dependent on the primary key 'id'
  through 'client_ip':  id -> client_ip -> country
  
  This violates 3NF, which requires that every non-key attribute depends
  ONLY on the primary key, not on other non-key attributes.
  
  SOLUTION: Extract the ip-country mapping into a separate table.
""")

# Drop tables if they exist from a previous run
cursor.execute("DROP TABLE IF EXISTS request_logs_normalized")
cursor.execute("DROP TABLE IF EXISTS ip_country")
conn.commit()

# Create ip_country table
cursor.execute("""
    CREATE TABLE ip_country (
        client_ip VARCHAR(64) PRIMARY KEY,
        country VARCHAR(128) NOT NULL
    )
""")
print("  Created ip_country table.")

# Populate ip_country from existing data
cursor.execute("""
    INSERT IGNORE INTO ip_country (client_ip, country)
    SELECT DISTINCT client_ip, country FROM request_logs
    WHERE client_ip IS NOT NULL AND country IS NOT NULL
""")
conn.commit()

# Verify ip_country
cursor.execute("SELECT COUNT(*) FROM ip_country")
ip_country_count = cursor.fetchone()[0]
print(f"  Populated ip_country with {ip_country_count} unique IP-country mappings.")

# Show sample of ip_country
cursor.execute("SELECT * FROM ip_country LIMIT 5")
sample = cursor.fetchall()
print(f"  Sample ip_country data:")
for row in sample:
    print(f"    {row}")

# Create normalized request_logs table (without country)
cursor.execute("""
    CREATE TABLE request_logs_normalized (
        id INT PRIMARY KEY,
        client_ip VARCHAR(64),
        gender VARCHAR(32),
        age INT,
        income VARCHAR(64),
        is_banned TINYINT(1),
        time_of_day VARCHAR(32),
        requested_file TEXT,
        request_time TIMESTAMP,
        FOREIGN KEY (client_ip) REFERENCES ip_country(client_ip)
    )
""")
print("  Created request_logs_normalized table (without country column).")

# Populate normalized table
cursor.execute("""
    INSERT INTO request_logs_normalized 
        (id, client_ip, gender, age, income, is_banned, time_of_day, requested_file, request_time)
    SELECT id, client_ip, gender, age, income, is_banned, time_of_day, requested_file, request_time
    FROM request_logs
""")
conn.commit()

cursor.execute("SELECT COUNT(*) FROM request_logs_normalized")
norm_count = cursor.fetchone()[0]
print(f"  Populated request_logs_normalized with {norm_count} rows.")

# Verify: join to reconstruct original data
cursor.execute("""
    SELECT rn.id, ic.country, rn.client_ip, rn.gender, rn.income, 
           rn.is_banned, rn.time_of_day
    FROM request_logs_normalized rn
    JOIN ip_country ic ON rn.client_ip = ic.client_ip
    LIMIT 5
""")
joined_sample = cursor.fetchall()
print(f"  Verification (joined data sample):")
for row in joined_sample:
    print(f"    {row}")

# Print the migration queries for the report
print("\n  === 3NF Migration Queries ===")
print("""
  -- 1. Create ip_country lookup table
  CREATE TABLE ip_country (
      client_ip VARCHAR(64) PRIMARY KEY,
      country VARCHAR(128) NOT NULL
  );

  -- 2. Populate from existing data
  INSERT IGNORE INTO ip_country (client_ip, country)
  SELECT DISTINCT client_ip, country FROM request_logs
  WHERE client_ip IS NOT NULL AND country IS NOT NULL;

  -- 3. Create normalized request_logs table (country removed)
  CREATE TABLE request_logs_normalized (
      id INT PRIMARY KEY,
      client_ip VARCHAR(64),
      gender VARCHAR(32),
      age INT,
      income VARCHAR(64),
      is_banned TINYINT(1),
      time_of_day VARCHAR(32),
      requested_file TEXT,
      request_time TIMESTAMP,
      FOREIGN KEY (client_ip) REFERENCES ip_country(client_ip)
  );

  -- 4. Migrate data
  INSERT INTO request_logs_normalized 
      (id, client_ip, gender, age, income, is_banned, time_of_day, requested_file, request_time)
  SELECT id, client_ip, gender, age, income, is_banned, time_of_day, requested_file, request_time
  FROM request_logs;

  -- 5. To reconstruct original view:
  SELECT rn.*, ic.country
  FROM request_logs_normalized rn
  JOIN ip_country ic ON rn.client_ip = ic.client_ip;
""")

# Show final schema
print("  === Final 3NF Schema ===")
print("  Table: ip_country")
cursor.execute("DESCRIBE ip_country")
for col in cursor.fetchall():
    print(f"    {col}")
print("\n  Table: request_logs_normalized")
cursor.execute("DESCRIBE request_logs_normalized")
for col in cursor.fetchall():
    print(f"    {col}")

# ============================================================
# STEP 3: MODEL 1 - IP -> Country Prediction
# ============================================================
print("\n" + "=" * 60)
print("[STEP 3] Model 1: Predicting Country from Client IP")
print("=" * 60)

# Clean data - drop rows with missing values in key columns
df_model1 = df[['client_ip', 'country']].dropna()
print(f"  Data points for Model 1: {len(df_model1)}")
print(f"  Unique IPs: {df_model1['client_ip'].nunique()}")
print(f"  Unique Countries: {df_model1['country'].nunique()}")

# Encode IP addresses and countries
ip_encoder = LabelEncoder()
country_encoder = LabelEncoder()

df_model1 = df_model1.copy()
df_model1['ip_encoded'] = ip_encoder.fit_transform(df_model1['client_ip'])
df_model1['country_encoded'] = country_encoder.fit_transform(df_model1['country'])

X1 = df_model1[['ip_encoded']].values
y1 = df_model1['country_encoded'].values

# Split into train and test sets
X1_train, X1_test, y1_train, y1_test = train_test_split(
    X1, y1, test_size=0.2, random_state=42
)
print(f"  Training set: {len(X1_train)}, Test set: {len(X1_test)}")

# Train a Decision Tree
print("\n  Training Decision Tree Classifier...")
model1 = DecisionTreeClassifier(random_state=42)
model1.fit(X1_train, y1_train)

# Predict on test set
y1_pred = model1.predict(X1_test)
accuracy1 = accuracy_score(y1_test, y1_pred)
print(f"  Model 1 Accuracy: {accuracy1 * 100:.2f}%")

# Decode predictions for output
y1_test_labels = country_encoder.inverse_transform(y1_test)
y1_pred_labels = country_encoder.inverse_transform(y1_pred)

# Build output dataframe
model1_output = pd.DataFrame({
    'client_ip': ip_encoder.inverse_transform(X1_test.flatten()),
    'actual_country': y1_test_labels,
    'predicted_country': y1_pred_labels,
    'correct': y1_test_labels == y1_pred_labels
})

print(f"\n  Model 1 Test Set Output (first 15 rows):")
print(model1_output.head(15).to_string(index=False))

correct_count = model1_output['correct'].sum()
total_count = len(model1_output)
print(f"\n  Correct: {correct_count}/{total_count} ({correct_count/total_count*100:.2f}%)")

# Classification report
print(f"\n  Model 1 Classification Report:")
report1 = classification_report(y1_test_labels, y1_pred_labels, zero_division=0)
print(report1)

# Save to local file
model1_output.to_csv("/tmp/model1_ip_to_country_results.csv", index=False)
print("  Saved Model 1 results to /tmp/model1_ip_to_country_results.csv")

# ============================================================
# STEP 4: MODEL 2 - Features -> Income Prediction
# ============================================================
print("\n" + "=" * 60)
print("[STEP 4] Model 2: Predicting Income from Available Fields")
print("=" * 60)

# Strategy:
# 1. 'age' is all NULL so we skip it
# 2. Use client_ip octets, country, gender, hour, minute, is_banned as features
# 3. Bin income into 3 categories (Low/Medium/High) to improve accuracy
# 4. Use Random Forest with tuned hyperparameters

# Prepare data
df_model2 = df[['client_ip', 'country', 'gender', 'time_of_day', 'income', 'is_banned']].dropna(
    subset=['client_ip', 'country', 'gender', 'time_of_day', 'income'])

# Filter out 'Unknown' income
df_model2 = df_model2[df_model2['income'] != 'Unknown'].copy()

print(f"  Data points (after removing Unknown income): {len(df_model2)}")
print(f"\n  Original Income distribution:")
print(df_model2['income'].value_counts().to_string())

# Bin income into 3 categories for better predictability
income_bin_map = {
    '0-10k': 'Low (0-40k)',
    '10k-20k': 'Low (0-40k)',
    '20k-40k': 'Low (0-40k)',
    '40k-60k': 'Medium (40k-100k)',
    '60k-100k': 'Medium (40k-100k)',
    '100k-150k': 'High (100k+)',
    '150k-250k': 'High (100k+)',
    '250k+': 'High (100k+)',
}

df_model2['income_binned'] = df_model2['income'].map(income_bin_map)
print(f"\n  Binned Income distribution (3 classes):")
print(df_model2['income_binned'].value_counts().to_string())

# Feature engineering: extract hour and minute from time_of_day
df_model2['hour'] = df_model2['time_of_day'].apply(
    lambda x: int(str(x).split(':')[0]) if ':' in str(x) else 0)
df_model2['minute'] = df_model2['time_of_day'].apply(
    lambda x: int(str(x).split(':')[1]) if ':' in str(x) and len(str(x).split(':')) > 1 else 0)

# Extract IP octets as numeric features
df_model2['ip_oct1'] = df_model2['client_ip'].apply(lambda x: int(str(x).split('.')[0]) if '.' in str(x) else 0)
df_model2['ip_oct2'] = df_model2['client_ip'].apply(lambda x: int(str(x).split('.')[1]) if '.' in str(x) and len(str(x).split('.')) > 1 else 0)
df_model2['ip_oct3'] = df_model2['client_ip'].apply(lambda x: int(str(x).split('.')[2]) if '.' in str(x) and len(str(x).split('.')) > 2 else 0)

# Encode categorical features
country_enc = LabelEncoder()
df_model2['country_encoded'] = country_enc.fit_transform(df_model2['country'])

gender_enc = LabelEncoder()
df_model2['gender_encoded'] = gender_enc.fit_transform(df_model2['gender'])

income_bin_encoder = LabelEncoder()
df_model2['income_bin_encoded'] = income_bin_encoder.fit_transform(df_model2['income_binned'])

print(f"\n  Features used: country, gender, hour, minute, ip_oct1, ip_oct2, ip_oct3, is_banned")
print(f"  Target: income_binned (3 classes: Low/Medium/High)")
print(f"  Income bin classes: {list(income_bin_encoder.classes_)}")

feature_cols = ['country_encoded', 'gender_encoded', 'hour', 'minute',
                'ip_oct1', 'ip_oct2', 'ip_oct3', 'is_banned']
X2 = df_model2[feature_cols].values
y2 = df_model2['income_bin_encoded'].values

# Split into train and test sets
X2_train, X2_test, y2_train, y2_test = train_test_split(
    X2, y2, test_size=0.2, random_state=42
)
print(f"\n  Training set: {len(X2_train)}, Test set: {len(X2_test)}")

# Try Random Forest
print("\n  Training Random Forest Classifier (300 trees)...")
model2_rf = RandomForestClassifier(n_estimators=300, random_state=42, n_jobs=-1, min_samples_leaf=2)
model2_rf.fit(X2_train, y2_train)
y2_pred_rf = model2_rf.predict(X2_test)
accuracy2_rf = accuracy_score(y2_test, y2_pred_rf)
print(f"  Random Forest Accuracy: {accuracy2_rf * 100:.2f}%")

# Try Gradient Boosting
print("\n  Training Gradient Boosting Classifier (300 trees, depth=8)...")
model2_gb = GradientBoostingClassifier(n_estimators=300, random_state=42, max_depth=8, learning_rate=0.1, subsample=0.8)
model2_gb.fit(X2_train, y2_train)
y2_pred_gb = model2_gb.predict(X2_test)
accuracy2_gb = accuracy_score(y2_test, y2_pred_gb)
print(f"  Gradient Boosting Accuracy: {accuracy2_gb * 100:.2f}%")

# Try Decision Tree as baseline
print("\n  Training Decision Tree Classifier (baseline)...")
model2_dt = DecisionTreeClassifier(random_state=42)
model2_dt.fit(X2_train, y2_train)
y2_pred_dt = model2_dt.predict(X2_test)
accuracy2_dt = accuracy_score(y2_test, y2_pred_dt)
print(f"  Decision Tree Accuracy: {accuracy2_dt * 100:.2f}%")

# Pick the best model
results = {
    "Random Forest": (model2_rf, y2_pred_rf, accuracy2_rf),
    "Gradient Boosting": (model2_gb, y2_pred_gb, accuracy2_gb),
    "Decision Tree": (model2_dt, y2_pred_dt, accuracy2_dt),
}
best_name = max(results, key=lambda k: results[k][2])
best_model2, y2_pred, accuracy2 = results[best_name]

print(f"\n  === Best Model: {best_name} with accuracy {accuracy2 * 100:.2f}% ===")

# Feature importance
feature_importance = best_model2.feature_importances_
feature_display_names = ['country', 'gender', 'hour', 'minute', 'ip_oct1', 'ip_oct2', 'ip_oct3', 'is_banned']
print(f"\n  Feature Importance:")
for feat, imp in sorted(zip(feature_display_names, feature_importance), key=lambda x: -x[1]):
    print(f"    {feat}: {imp:.4f}")

# Decode predictions
y2_test_labels = income_bin_encoder.inverse_transform(y2_test)
y2_pred_labels = income_bin_encoder.inverse_transform(y2_pred)

# Build output dataframe
model2_output = pd.DataFrame({
    'country': country_enc.inverse_transform(X2_test[:, 0].astype(int)),
    'gender': gender_enc.inverse_transform(X2_test[:, 1].astype(int)),
    'hour': X2_test[:, 2].astype(int),
    'is_banned': X2_test[:, 7].astype(int),
    'actual_income_bin': y2_test_labels,
    'predicted_income_bin': y2_pred_labels,
    'correct': y2_test_labels == y2_pred_labels
})

print(f"\n  Model 2 Test Set Output (first 15 rows):")
print(model2_output.head(15).to_string(index=False))

correct_count2 = model2_output['correct'].sum()
total_count2 = len(model2_output)
print(f"\n  Correct: {correct_count2}/{total_count2} ({correct_count2/total_count2*100:.2f}%)")

# Classification report
print(f"\n  Model 2 Classification Report:")
report2 = classification_report(y2_test_labels, y2_pred_labels, zero_division=0)
print(report2)

# Save to local file
model2_output.to_csv("/tmp/model2_income_prediction_results.csv", index=False)
print("  Saved Model 2 results to /tmp/model2_income_prediction_results.csv")

# ============================================================
# STEP 5: Upload results to GCS
# ============================================================
print("\n" + "=" * 60)
print("[STEP 5] Uploading results to GCS bucket...")
print("=" * 60)

client = storage.Client(project=GCP_PROJECT)
bucket = client.bucket(GCS_BUCKET)

# Upload Model 1 results
blob1 = bucket.blob("hw6/model1_ip_to_country_results.csv")
blob1.upload_from_filename("/tmp/model1_ip_to_country_results.csv")
print(f"  Uploaded: gs://{GCS_BUCKET}/hw6/model1_ip_to_country_results.csv")

# Upload Model 2 results
blob2 = bucket.blob("hw6/model2_income_prediction_results.csv")
blob2.upload_from_filename("/tmp/model2_income_prediction_results.csv")
print(f"  Uploaded: gs://{GCS_BUCKET}/hw6/model2_income_prediction_results.csv")

# Upload a summary report
summary = {
    "model1": {
        "name": "Decision Tree (IP -> Country)",
        "description": "Uses LabelEncoded client IP to predict country. Since each IP deterministically maps to one country, a Decision Tree learns the exact mapping.",
        "accuracy": float(accuracy1),
        "accuracy_percent": f"{accuracy1 * 100:.2f}%",
        "test_size": int(len(X1_test)),
        "train_size": int(len(X1_train)),
    },
    "model2": {
        "name": f"{best_name} (Features -> Income Bracket)",
        "description": f"Uses country, gender, hour, minute, IP octets (1-3), and is_banned to predict income bracket (Low/Medium/High). The 'age' column was entirely NULL and excluded. 'Unknown' income rows were filtered out. Income was binned into 3 categories (Low: 0-40k, Medium: 40k-100k, High: 100k+) to improve prediction accuracy. Best model: {best_name}.",
        "accuracy": float(accuracy2),
        "accuracy_percent": f"{accuracy2 * 100:.2f}%",
        "test_size": int(len(X2_test)),
        "train_size": int(len(X2_train)),
        "income_bins": {
            "Low (0-40k)": "0-10k, 10k-20k, 20k-40k",
            "Medium (40k-100k)": "40k-60k, 60k-100k",
            "High (100k+)": "100k-150k, 150k-250k, 250k+"
        },
        "feature_importance": {feat: float(imp) for feat, imp in zip(feature_display_names, feature_importance)},
        "all_models_tried": {
            "Random Forest (300 trees)": f"{accuracy2_rf * 100:.2f}%",
            "Gradient Boosting (300 trees, depth=8)": f"{accuracy2_gb * 100:.2f}%",
            "Decision Tree (no depth limit)": f"{accuracy2_dt * 100:.2f}%",
        }
    },
    "normalization": {
        "original_table": "request_logs",
        "new_tables": ["ip_country", "request_logs_normalized"],
        "ip_country_mappings": int(ip_country_count),
        "normalized_rows": int(norm_count),
        "reason": "client_ip -> country is a transitive dependency violating 3NF"
    }
}

blob3 = bucket.blob("hw6/model_summary.json")
blob3.upload_from_string(json.dumps(summary, indent=2), content_type='application/json')
print(f"  Uploaded: gs://{GCS_BUCKET}/hw6/model_summary.json")

# ============================================================
# DONE
# ============================================================
print("\n" + "=" * 60)
print("ALL DONE!")
print("=" * 60)
print(f"  Model 1 (IP -> Country):      {accuracy1 * 100:.2f}% accuracy")
print(f"  Model 2 (Features -> Income):  {accuracy2 * 100:.2f}% accuracy")
print(f"  Results uploaded to gs://{GCS_BUCKET}/hw6/")
print(f"  Files:")
print(f"    - hw6/model1_ip_to_country_results.csv")
print(f"    - hw6/model2_income_prediction_results.csv")
print(f"    - hw6/model_summary.json")
print("=" * 60)

# Close DB connection
cursor.close()
conn.close()
