


-  when displaying a document, try and display the summary with rating etc. If not available, display the abstract and offer a button to create the summary from it.

research_questions:
id serial primary key
user_id integer references users(id)
project_id integer references projects(id)
question text not null
question_embedding vector(1024)
best_answer text
answered_by integer references evaluators(id)
created_at timestamp default current_timestamp
updated_at timestamp default current_timestamp
deleted_at timestamp
deleted_by integer references evaluators(id)

#a table to add search strategies, eg keywords, semantic, semantic_hyde, semantic_sqa, bm25
search_strategies:
id serial primary key
name text not null
description text
created_at timestamp default current_timestamp
updated_at timestamp default current_timestamp
deleted_at timestamp
deleted_by integer references evaluators(id)


# a table to store all the references found for a research question
research_question_references:
id serial primary key
document_id integer references documents(id)
found_by_strategy integer references search_strategies(id)
rating integer
rated_by integer references evaluators(id)
created_at timestamp default current_timestamp
updated_at timestamp default current_timestamp
deleted_at timestamp
deleted_by integer references evaluators(id)
