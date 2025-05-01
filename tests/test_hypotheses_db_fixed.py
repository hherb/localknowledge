"""
Test script for the HypothesesDatabaseManager and ResearchQuestionsManager.

This script tests the basic functionality of the HypothesesDatabaseManager and
ResearchQuestionsManager classes.
"""
import sys
import os
from datetime import datetime

# Add the parent directory to the path so we can import the localknowledge package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from localknowledge.db.hypotheses import HypothesesDatabaseManager
from localknowledge.db.research_questions import ResearchQuestionsManager
from localknowledge.db.project import ProjectDatabaseManager
from localknowledge.db.base import DatabaseManager


def test_hypotheses_manager():
    """Test basic functionality of the HypothesesDatabaseManager."""
    # Create managers
    hypotheses_db = HypothesesDatabaseManager()
    project_db = ProjectDatabaseManager()
    db = DatabaseManager()
    
    # Use existing user "hherb"
    query = "SELECT id FROM users WHERE username = 'hherb'"
    result = db.execute(query)
    if result and len(result) > 0:
        user_id = result[0]['id']
    else:
        print("User 'hherb' not found. Using user_id = 1 as fallback.")
        user_id = 1
    
    # Create a test project
    project_id = project_db.create_project(
        title="Test Project for Hypotheses",
        description="A project for testing hypotheses functionality",
        manager_id=user_id
    )
    
    # Test creating a hypothesis
    hypothesis_id = hypotheses_db.create_hypothesis(
        hypothesis="Test hypothesis",
        counterhypothesis="Test counter-hypothesis"
    )
    assert hypothesis_id is not None, "Failed to create hypothesis"
    
    # Test getting a hypothesis
    hypothesis = hypotheses_db.get_hypothesis(hypothesis_id)
    assert hypothesis is not None, "Failed to get hypothesis"
    assert hypothesis["hypothesis"] == "Test hypothesis", "Hypothesis text doesn't match"
    
    # Test updating a hypothesis
    update_result = hypotheses_db.update_hypothesis(
        hypothesis_id=hypothesis_id,
        data={"hypothesis": "Updated test hypothesis"}
    )
    assert update_result is True, "Failed to update hypothesis"
    
    # Verify the update
    updated_hypothesis = hypotheses_db.get_hypothesis(hypothesis_id)
    assert updated_hypothesis["hypothesis"] == "Updated test hypothesis", "Hypothesis update failed"
    
    # Test associating with a project
    association_result = hypotheses_db.associate_with_project(hypothesis_id, project_id)
    assert association_result is True, "Failed to associate hypothesis with project"
    
    # Test getting project hypotheses
    project_hypotheses = hypotheses_db.get_project_hypotheses(project_id)
    assert len(project_hypotheses) > 0, "Failed to get project hypotheses"
    assert project_hypotheses[0]["id"] == hypothesis_id, "Project hypothesis ID doesn't match"
    
    # Test getting projects for hypothesis
    hypothesis_projects = hypotheses_db.get_projects_for_hypothesis(hypothesis_id)
    assert len(hypothesis_projects) > 0, "Failed to get hypothesis projects"
    assert hypothesis_projects[0]["id"] == project_id, "Hypothesis project ID doesn't match"
    
    # Test searching hypotheses
    search_results = hypotheses_db.search_hypotheses("Updated")
    assert len(search_results) > 0, "Failed to search hypotheses"
    assert search_results[0]["id"] == hypothesis_id, "Search result ID doesn't match"
    
    # Test removing from project
    removal_result = hypotheses_db.remove_from_project(hypothesis_id, project_id)
    assert removal_result is True, "Failed to remove hypothesis from project"
    
    # Verify removal
    project_hypotheses_after = hypotheses_db.get_project_hypotheses(project_id)
    assert len(project_hypotheses_after) == 0, "Hypothesis still associated with project after removal"
    
    # Test deleting a hypothesis
    delete_result = hypotheses_db.delete_hypothesis(hypothesis_id)
    assert delete_result is True, "Failed to delete hypothesis"
    
    # Verify deletion
    deleted_hypothesis = hypotheses_db.get_hypothesis(hypothesis_id)
    assert deleted_hypothesis is None, "Hypothesis still exists after deletion"
    
    # Clean up
    project_db.delete_project(project_id)
    print("HypothesesDatabaseManager tests passed!")


def test_research_questions_manager():
    """Test basic functionality of the ResearchQuestionsManager."""
    # Create managers
    questions_db = ResearchQuestionsManager()
    project_db = ProjectDatabaseManager()
    db = DatabaseManager()
    
    # Use existing user "hherb"
    query = "SELECT id FROM users WHERE username = 'hherb'"
    result = db.execute(query)
    if result and len(result) > 0:
        user_id = result[0]['id']
    else:
        print("User 'hherb' not found. Using user_id = 1 as fallback.")
        user_id = 1
    
    # Create a test project
    project_id = project_db.create_project(
        title="Test Project for Research Questions",
        description="A project for testing research questions functionality",
        manager_id=user_id
    )
    
    # Test creating a research question
    question_id = questions_db.create_question(
        question="Test research question?",
        details="Details about the test research question"
    )
    assert question_id is not None, "Failed to create research question"
    
    # Test getting a research question
    question = questions_db.get_question(question_id)
    assert question is not None, "Failed to get research question"
    assert question["question"] == "Test research question?", "Question text doesn't match"
    
    # Test updating a research question
    update_result = questions_db.update_question(
        question_id=question_id,
        data={"question": "Updated test research question?"}
    )
    assert update_result is True, "Failed to update research question"
    
    # Verify the update
    updated_question = questions_db.get_question(question_id)
    assert updated_question["question"] == "Updated test research question?", "Question update failed"
    
    # Test associating with a project
    association_result = questions_db.associate_with_project(question_id, project_id)
    assert association_result is True, "Failed to associate question with project"
    
    # Test getting project questions
    project_questions = questions_db.get_project_questions(project_id)
    assert len(project_questions) > 0, "Failed to get project questions"
    assert project_questions[0]["id"] == question_id, "Project question ID doesn't match"
    
    # Test getting projects for question
    question_projects = questions_db.get_projects_for_question(question_id)
    assert len(question_projects) > 0, "Failed to get question projects"
    assert question_projects[0]["id"] == project_id, "Question project ID doesn't match"
    
    # Test searching questions
    search_results = questions_db.search_questions("Updated")
    assert len(search_results) > 0, "Failed to search questions"
    assert search_results[0]["id"] == question_id, "Search result ID doesn't match"
    
    # Test removing from project
    removal_result = questions_db.remove_from_project(question_id, project_id)
    assert removal_result is True, "Failed to remove question from project"
    
    # Verify removal
    project_questions_after = questions_db.get_project_questions(project_id)
    assert len(project_questions_after) == 0, "Question still associated with project after removal"
    
    # Test deleting a question
    delete_result = questions_db.delete_question(question_id)
    assert delete_result is True, "Failed to delete question"
    
    # Verify deletion
    deleted_question = questions_db.get_question(question_id)
    assert deleted_question is None, "Question still exists after deletion"
    
    # Clean up
    project_db.delete_project(project_id)
    print("ResearchQuestionsManager tests passed!")


if __name__ == "__main__":
    print("Testing HypothesesDatabaseManager...")
    test_hypotheses_manager()
    
    print("\nTesting ResearchQuestionsManager...")
    test_research_questions_manager()
    
    print("\nAll tests passed!")
