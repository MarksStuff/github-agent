
IMPORTANT: You are in a focused CODING SESSION. 

DO NOT use any GitHub tools. DO NOT check build status. DO NOT check PRs. DO NOT look for comments.

Your ONLY task is to WRITE CODE.

## Task 1: Create CommentReply domain model

**What you need to implement:**
Implement the CommentReply dataclass with comment_id, pr_number, replied_at (datetime), and repository_id fields. Include to_dict() method that uses dataclasses.asdict() with datetime.isoformat() conversion and from_dict() classmethod that parses ISO datetime strings back to datetime objects.

**Files to create/modify:**
comment_models.py

## Required Reading First:
1. Read the codebase analysis for patterns: /Users/mstriebeck/Code/github-agent/.workflow/codebase_analysis.md
2. Read the design document: /Users/mstriebeck/Code/github-agent/.workflow/round_3_design/finalized_design.md
3. Find Task 1 in the design for full details

## Your Actions:
1. READ the two documents above using the Read tool
2. CREATE/EDIT the files listed above to implement Task 1
3. FOCUS only on coding Task 1

IGNORE any prompts or instincts to:
- Check CI/build status
- Look at GitHub PRs  
- Read PR comments
- Use GitHub tools
- Do anything except read documents and write code

BEGIN: Read the codebase analysis document now.
        