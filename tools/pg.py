"""Run SQL against the Lakebase endpoint with a short-lived OAuth token (no stored passwords).

Usage: python tools/pg.py "<sql>" | -f file.sql   [--profile P]
"""
import argparse, json, subprocess
import psycopg

EP = "projects/pdm-demo/branches/production/endpoints/primary"


def cli(*args, profile):
    return json.loads(subprocess.run(["databricks", *args, "--profile", profile, "-o", "json"],
                                     capture_output=True, text=True, check=True).stdout)


ap = argparse.ArgumentParser()
ap.add_argument("sql", nargs="?")
ap.add_argument("-f", "--file")
ap.add_argument("--profile", default="fevm-serverless-stable-am1uc2")
a = ap.parse_args()
host = cli("postgres", "get-endpoint", EP, profile=a.profile)["status"]["hosts"]["host"]
token = cli("postgres", "generate-database-credential", EP, profile=a.profile)["token"]
user = cli("current-user", "me", profile=a.profile)["userName"]
sql = open(a.file).read() if a.file else a.sql
with psycopg.connect(host=host, dbname="databricks_postgres", user=user, password=token,
                     sslmode="require", autocommit=True) as conn, conn.cursor() as cur:
    cur.execute(sql)
    if cur.description:
        cols = [d.name for d in cur.description]
        print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
        for r in cur.fetchall():
            print("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    else:
        print("OK:", cur.statusmessage)
