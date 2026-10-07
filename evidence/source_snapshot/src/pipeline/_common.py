"""Pipeline-wide settings. Imported by every pipeline source file."""
import sys

from pyspark.sql import SparkSession

spark = SparkSession.getActiveSession()
sys.path.append(spark.conf.get("pdm.source_path"))

CATALOG = spark.conf.get("pdm.catalog")
RAW = f"{CATALOG}.pdm_raw"
ML = f"{CATALOG}.pdm_ml"
