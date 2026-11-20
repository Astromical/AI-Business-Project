PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS tijdslot (
    id   INTEGER PRIMARY KEY,
    dag  TEXT    NOT NULL CHECK (dag IN ('maandag','dinsdag','woensdag','donderdag','vrijdag')),
    uur  INTEGER NOT NULL CHECK (uur BETWEEN 1 AND 8),
    UNIQUE (dag, uur)
);

CREATE TABLE IF NOT EXISTS lokaal (
    id    TEXT  PRIMARY KEY,
    naam  TEXT  NOT NULL,
    type  TEXT  NOT NULL CHECK (type IN ('regulier','lab','gym'))
);

CREATE TABLE IF NOT EXISTS leraar (
    id                TEXT    PRIMARY KEY,
    naam              TEXT    NOT NULL,
    max_uren_per_dag  INTEGER NOT NULL CHECK (max_uren_per_dag BETWEEN 1 AND 8)
);

CREATE TABLE IF NOT EXISTS onbeschikbaar (
    leraar_id    TEXT    NOT NULL REFERENCES leraar(id) ON DELETE CASCADE,
    tijdslot_id  INTEGER NOT NULL REFERENCES tijdslot(id) ON DELETE CASCADE,
    PRIMARY KEY (leraar_id, tijdslot_id)
);

CREATE TABLE IF NOT EXISTS les (
    id               TEXT    PRIMARY KEY,
    vak              TEXT    NOT NULL,
    klas             TEXT    NOT NULL,
    leraar_id        TEXT    NOT NULL REFERENCES leraar(id),
    aantal_per_week  INTEGER NOT NULL CHECK (aantal_per_week > 0),
    lokaaltype       TEXT    NOT NULL CHECK (lokaaltype IN ('regulier','lab','gym'))
);

CREATE TABLE IF NOT EXISTS ingepland (
    les_id       TEXT    NOT NULL REFERENCES les(id) ON DELETE CASCADE,
    volgnummer   INTEGER NOT NULL,
    tijdslot_id  INTEGER NOT NULL REFERENCES tijdslot(id),
    lokaal_id    TEXT    NOT NULL REFERENCES lokaal(id),
    PRIMARY KEY (les_id, volgnummer)
);

CREATE TABLE IF NOT EXISTS gebruiker (
    naam             TEXT  PRIMARY KEY,
    wachtwoord_hash  TEXT  NOT NULL,
    rol              TEXT  NOT NULL CHECK (rol IN ('roostermaker','leraar')),
    leraar_id        TEXT  UNIQUE REFERENCES leraar(id) ON DELETE SET NULL
);
