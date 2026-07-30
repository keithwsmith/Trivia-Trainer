"""Command-line entry point for the Jeopardy trainer.

Examples:
  python main.py init-db
  python main.py pull-opentdb --subject "Science" --category-id 17 --count 50
  python main.py preload-all --count 2000
  python main.py quiz --subject "Science" --limit 10
  python main.py weak-subjects
"""
import argparse
from db.connection import run_schema_script
from sources.opentdb_client import OpenTDBClient
from db.loader import load_opentdb_results
from study.quiz import get_quiz_clues, record_attempt, weak_subjects, check_answer


def cmd_init_db(_args):
    run_schema_script()


def cmd_pull_opentdb(args):
    client = OpenTDBClient()
    if args.category_id:
        results = client.fetch_all_for_category(args.category_id, target_count=args.count)
    else:
        results, _ = client.fetch_questions(amount=min(args.count, 50), difficulty=args.difficulty)

    # opentdb's numeric category id, keyed by category name, so the loader
    # can stamp ExternalId on each category row (e.g. "History" -> "23").
    category_name_to_id = {c["name"]: c["id"] for c in client.get_categories()}

    n = load_opentdb_results(
        results, subject_name=args.subject, category_name_to_id=category_name_to_id
    )
    print(f"Loaded {n} Open Trivia DB questions into subject '{args.subject}'.")


def cmd_preload_all(args):
    client = OpenTDBClient()
    categories = client.get_categories()
    category_name_to_id = {c["name"]: c["id"] for c in categories}

    print(f"Found {len(categories)} Open Trivia DB categories. Target: {args.count} questions each.")
    print("This can take a while -- opentdb allows 50 questions/request, 1 request/5s.\n")

    summary = []
    grand_total = 0

    for i, cat in enumerate(categories, start=1):
        print(f"[{i}/{len(categories)}] {cat['name']} (id {cat['id']})")

        def on_progress(collected, target, name=cat["name"]):
            print(f"    {name}: {collected}/{target}", end="\r")

        results = client.fetch_all_for_category(
            cat["id"], target_count=args.count, on_progress=on_progress
        )
        print()  # newline after the \r progress line

        n = load_opentdb_results(
            results, subject_name=cat["name"], category_name_to_id=category_name_to_id
        )
        grand_total += n
        summary.append((cat["name"], n, args.count))

        status = "full" if n >= args.count else f"only {n} available"
        print(f"    Loaded {n} ({status}).\n")

    print("=" * 50)
    print(f"Done. {grand_total} questions loaded across {len(categories)} subjects.\n")
    shortfalls = [(name, n, target) for name, n, target in summary if n < target]
    if shortfalls:
        print("Categories that came in under the target (opentdb simply doesn't have more):")
        for name, n, target in shortfalls:
            print(f"  {name}: {n}/{target}")


def cmd_quiz(args):
    clues = get_quiz_clues(
        subject=args.subject,
        difficulty=args.difficulty,
        only_missed=args.only_missed,
        limit=args.limit,
    )
    if not clues:
        print("No clues matched. Try loading more data first.")
        return

    correct = 0
    for c in clues:
        print(f"\n[{c['CategoryName']}] {c['ClueText']}")
        answer = input("Your response: ")
        was_correct = check_answer(answer, c["CorrectResponse"])
        record_attempt(c["ClueId"], answer, was_correct)
        if was_correct:
            correct += 1
            print("Correct!")
        else:
            print(f"Missed. Correct response: {c['CorrectResponse']}")

    print(f"\nScore: {correct}/{len(clues)}")


def cmd_weak_subjects(args):
    for row in weak_subjects(limit=args.limit):
        acc = row["Accuracy"] * 100 if row["Accuracy"] is not None else 0
        print(f"{row['SubjectName']:<30} {row['Correct']}/{row['Total']}  ({acc:.1f}%)")


def build_parser():
    p = argparse.ArgumentParser(description="Jeopardy study trainer")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create tables in the Jeopardy database").set_defaults(func=cmd_init_db)

    pull = sub.add_parser("pull-opentdb", help="Pull questions from Open Trivia DB")
    pull.add_argument("--subject", required=True)
    pull.add_argument("--category-id", type=int, default=None)
    pull.add_argument("--difficulty", choices=["easy", "medium", "hard"], default=None)
    pull.add_argument("--count", type=int, default=50)
    pull.set_defaults(func=cmd_pull_opentdb)

    preload = sub.add_parser(
        "preload-all",
        help="Pull up to --count questions for every opentdb category, one subject each",
    )
    preload.add_argument("--count", type=int, default=2000)
    preload.set_defaults(func=cmd_preload_all)

    quiz = sub.add_parser("quiz", help="Run an interactive quiz")
    quiz.add_argument("--subject", default=None)
    quiz.add_argument("--difficulty", choices=["easy", "medium", "hard"], default=None)
    quiz.add_argument("--only-missed", action="store_true")
    quiz.add_argument("--limit", type=int, default=10)
    quiz.set_defaults(func=cmd_quiz)

    weak = sub.add_parser("weak-subjects", help="Show your lowest-accuracy subjects")
    weak.add_argument("--limit", type=int, default=10)
    weak.set_defaults(func=cmd_weak_subjects)

    return p


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
