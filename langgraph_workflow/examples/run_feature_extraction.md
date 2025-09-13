# Running the Feature Extraction Node

There are several ways to run the workflow just to the feature extraction node or to specific points:

## Method 1: Run Only Feature Extraction Node (Single Step)

```bash
# Run ONLY the extract_feature node with a simple feature
python langgraph_workflow/run.py \
  --repo-path /path/to/your/repo \
  --feature "Add user authentication system" \
  --step extract_feature

# Run ONLY the extract_feature node with a PRD file
python langgraph_workflow/run.py \
  --repo-path /path/to/your/repo \
  --feature-file /path/to/prd.md \
  --step extract_feature

# Run ONLY the extract_feature node with a specific feature from PRD
python langgraph_workflow/run.py \
  --repo-path /path/to/your/repo \
  --feature-file /path/to/prd.md \
  --feature-name "OAuth Integration" \
  --step extract_feature
```

## Method 2: Progressive Execution (Stop After Feature Extraction)

```bash
# Run workflow and stop after the first step (extract_feature)
python langgraph_workflow/run.py \
  --repo-path /path/to/your/repo \
  --feature "Add user authentication system" \
  --stop-after 1

# Or use the step name explicitly
python langgraph_workflow/run.py \
  --repo-path /path/to/your/repo \
  --feature "Add user authentication system" \
  --stop-after extract_feature

# Run first 2 steps (extract_feature + extract_code_context)
python langgraph_workflow/run.py \
  --repo-path /path/to/your/repo \
  --feature "Add user authentication system" \
  --stop-after 2
```

## Method 3: Interactive Step-by-Step Mode

```bash
# Run in interactive mode where you control each step
python langgraph_workflow/run.py --step-mode

# The system will prompt you:
# - Enter repository path
# - Enter feature description
# - Then ask before each step if you want to continue
```

## Method 4: Resume from Checkpoint

```bash
# First run (stop after feature extraction)
python langgraph_workflow/run.py \
  --repo-path /path/to/your/repo \
  --feature "Add user authentication system" \
  --thread-id my-feature-123 \
  --stop-after extract_feature

# Later, resume from where you left off
python langgraph_workflow/run.py \
  --repo-path /path/to/your/repo \
  --feature "Add user authentication system" \
  --thread-id my-feature-123 \
  --resume

# Or resume and stop at a specific later step
python langgraph_workflow/run.py \
  --repo-path /path/to/your/repo \
  --feature "Add user authentication system" \
  --thread-id my-feature-123 \
  --resume \
  --stop-after extract_code_context
```

## List Available Steps

```bash
# See all available workflow steps
python langgraph_workflow/run.py --list-steps

# Output:
# Available workflow steps:
#   1. extract_feature
#   2. extract_code_context
#   3. parallel_design_exploration
#   4. architect_synthesis
#   5. code_investigation
#   6. human_review
#   7. create_design_document
#   8. iterate_design_document
#   9. finalize_design_document
#  10. create_skeleton
#  11. parallel_development
#  12. reconciliation
#  13. component_tests
#  14. integration_tests
#  15. refinement
```

## Checking the Feature Artifact

After running the feature extraction node, you can find the stored feature at:

```bash
# The feature is stored as an artifact
~/.local/share/github-agent/langgraph/artifacts/<thread-id>/feature_description.md

# For example:
cat ~/.local/share/github-agent/langgraph/artifacts/my-feature-123/feature_description.md
```

## Example: Testing Feature Extraction

```bash
# 1. Create a test PRD file
cat > test_prd.md << 'EOF'
# Product Requirements Document

## Feature 1: User Authentication
- Users can register with email and password
- Email verification required
- Password reset via email
- Session management with JWT tokens

## Feature 2: User Profile
- Users can update profile information
- Profile photo upload
- Privacy settings
EOF

# 2. Run just feature extraction for Feature 1
python langgraph_workflow/run.py \
  --repo-path . \
  --feature-file test_prd.md \
  --feature-name "User Authentication" \
  --step extract_feature

# 3. Check the extracted feature artifact
ls ~/.local/share/github-agent/langgraph/artifacts/*/feature_description.md
```

## Pro Tips

1. **Use `--step` for testing individual nodes** - Great for development and debugging
2. **Use `--stop-after` for progressive workflows** - Run multiple steps but stop at a checkpoint
3. **Always specify `--thread-id` if you plan to resume** - This ensures checkpointing works
4. **Check artifacts directory** - All extracted features are saved there for reference

## Programmatic Usage

You can also run this programmatically:

```python
from langgraph_workflow.run import execute_single_step
from langgraph_workflow.langgraph_workflow import MultiAgentWorkflow

# Run just the feature extraction
result = await execute_single_step(
    MultiAgentWorkflow,
    "extract_feature",
    repo_path="/path/to/repo",
    feature_description="Add user authentication",
    thread_id="test-123"
)

# Check the result
print(f"Feature stored at: {result['artifacts_index']['feature_description']}")
```