CREATE TABLE IF NOT EXISTS names (
    nconst VARCHAR(12) PRIMARY KEY,
    primary_name VARCHAR(256),
    birth_year INT,
    death_year INT,
    primary_profession VARCHAR(256)
);

CREATE TABLE IF NOT EXISTS movies (
    tconst VARCHAR(12) PRIMARY KEY,
    primary_title VARCHAR(512) NOT NULL,
    original_title VARCHAR(512),
    start_year INT,
    runtime_minutes INT,
    genres VARCHAR(256),
    average_rating DECIMAL(3,1),
    num_votes INT,
    director_names TEXT,
    soup TEXT
);

CREATE TABLE IF NOT EXISTS principals (
    tconst VARCHAR(12),
    ordering INT,
    nconst VARCHAR(12),
    category VARCHAR(64),
    job TEXT,
    characters TEXT,
    PRIMARY KEY (tconst, ordering)
);

CREATE TABLE IF NOT EXISTS search_history (
    id SERIAL PRIMARY KEY,
    search_query VARCHAR(512) NOT NULL,
    matched_title VARCHAR(512),
    searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
