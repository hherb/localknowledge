CREATE TABLE IF NOT EXISTS hypotheses (
	id SERIAL PRIMARY KEY,
	hypothesis TEXT NOT NULL,
	counterhypothesis TEXT,
	created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX hypotheses_hypothesis_idx ON hypotheses USING GIN (to_tsvector('english', hypothesis));

CREATE TABLE IF NOT EXISTS hypotheses_projects (
	project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
	hypothesis_id INTEGER REFERENCES hypotheses(id) ON DELETE CASCADE,
	PRIMARY KEY (project_id, hypothesis_id)
);

CREATE TABLE IF NOT EXISTS research_questions (
	id SERIAL PRIMARY KEY,
	question TEXT NOT NULL,
	details TEXT
);

CREATE TABLE IF NOT EXISTS project_questions (
	project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
	research_question_id INTEGER REFERENCES research_questions(id) ON DELETE CASCADE,
	PRIMARY KEY (project_id, research_question_id)
);

CREATE INDEX idx_hypotheses_projects_project ON hypotheses_projects(project_id);
CREATE INDEX idx_hypotheses_projects_hypothesis ON hypotheses_projects(hypothesis_id);
CREATE INDEX idx_project_questions_project ON project_questions(project_id);