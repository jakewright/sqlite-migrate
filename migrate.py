import argparse
import os
import re
import sqlite3

parser = argparse.ArgumentParser()
parser.add_argument("command", nargs='*', help="the migration command to run [up, version]")
parser.add_argument("-v", "--verbose", action='count')
args = parser.parse_args()

# Define a *very* simple logging function
verbose_level = args.verbose
def log(message):
    if verbose_level:
        print(message)

# Open a connection to the database
database_path = os.environ['DATABASE']
conn = sqlite3.connect(database_path)
c = conn.cursor()

# Create migration table if not exists
log("Creating migrations table if not exists")
c.execute('''
    CREATE TABLE IF NOT EXISTS migration (
        migration_id INTEGER PRIMARY KEY,
        version TEXT NOT NULL UNIQUE,
        description TEXT,
        dirty INTEGER,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        deleted_at TEXT)
    ''')

def help():
    print("Available commands: up, version")

def version():
    """Read the current version from the database"""

    global c, version_info

    # Check for a cached version of the version
    if 'version_info' in globals():
        return version_info

    log("Reading current schema version")
    c.execute("SELECT version, dirty FROM migration ORDER BY migration_id DESC LIMIT 1")
    row = c.fetchone()

    if not row:
        current_version = None
        dirty = None
        log("Could not find a version in the database")
    else:
        current_version = row[0]
        dirty = row[1]
        log("Found version: " + current_version)

    version_info = {'version': current_version, 'dirty': dirty}
    return version_info

def extractMigrationInformation(filename: str, direction: str):
    """Extract the version from a filename e.g. V1.0.3.up.sql -> V1.0.3"""
    match = re.search("(?P<version>[^_]*)_?(?P<description>.*)\." + direction + "\.sql", filename, re.IGNORECASE)
    if not match:
        return {'version': None, 'description': None}
    return {'version': match.group('version'), 'description': match.group('description')}

def shouldApplyMigration(migration_filename: str, target_version=None):
    current_version = version()['version'] or ''

    # If we're already on the target version, don't apply the migration
    if target_version and target_version == current_version:
        return False

    # If there's no target version, assume we're migrating up to the latest version
    if not target_version or target_version > current_version:
        direction = 'up'
    else:
        direction = 'down'

    # Extract the proposed version from the migration filename
    proposed_version = extractMigrationInformation(migration_filename, direction)['version']

    # Don't apply this migration if the file does not have a valid version in the name
    if not proposed_version:
        return False

    if direction == 'up':
        if proposed_version <= current_version: return False
        if target_version and proposed_version > target_version: return False
    else:
        if proposed_version >= current_version: return False
        if target_version and proposed_version < target_version: return False

    return True

command = next(iter(args.command or []), None)

if command == 'version':
    current_version = version()['version']
    if not current_version:
        print("No version available")
    else:
        print("Current version: " + current_version)

elif command == 'up':
    # Stop if latest version is dirty
    if (version()['dirty']):
        print("Latest version is dirty. Please manually correct.")
        exit()

    # Get valid migration files to apply
    migration_filenames = list(filter(shouldApplyMigration, os.listdir('/migrations')))

    # Sort the migrations based on the version encoded in the filename
    migration_filenames.sort(key=lambda file: extractMigrationInformation(file, 'up')['version'])

    for migration_filename in migration_filenames:

        info = extractMigrationInformation(migration_filename, 'up')

        log("Applying migration " + migration_filename)
        c.execute("INSERT INTO migration (version, description, dirty) VALUES (?, ?, 1)", (info['version'], info['description'],))
        conn.commit()
        with open('/migrations/' + migration_filename, 'r') as f:
            sql = f.read()
            c.execute(sql)
        c.execute("UPDATE migration SET dirty = 0 WHERE migration_id = ?", (c.lastrowid,))
        conn.commit()

else:
    print("Unknown command")
    help()
