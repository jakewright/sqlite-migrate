# SQLite Schema Migration

A python script to migrate a SQLite database schema

## Usage

`docker-compose.yml` file:
```
migrate:
  image: jakewright/sqlite-migrate
  volumes:
    ./migrations:/migrations
  environment:
    DATABASE: ./database.db
```
