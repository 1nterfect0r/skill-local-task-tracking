import argparse
import json
import sys
from errors import TaskTrackingError, ValidationError
import service


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValidationError(message)


def _print(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.write("\n")


def main(argv=None):
    parser = JsonArgumentParser(prog="task-tracking")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-project")
    p_init.add_argument("project_id")
    p_init.add_argument("--statuses", default="backlog,open,done")

    p_add = sub.add_parser("add")
    p_add.add_argument("project_id")
    p_add.add_argument("--task-id", required=True)
    p_add.add_argument("--status")
    p_add.add_argument("--body")
    p_add.add_argument("--tags")
    p_add.add_argument("--assignee")
    p_add.add_argument("--priority")
    p_add.add_argument("--due-date")

    p_list = sub.add_parser("list")
    p_list.add_argument("project_id")
    p_list.add_argument("--status")
    p_list.add_argument("--tag")
    p_list.add_argument("--assignee")
    p_list.add_argument("--priority")
    p_list.add_argument("--fields")
    p_list.add_argument("--limit", type=int, default=100)
    p_list.add_argument("--offset", type=int, default=0)
    p_list.add_argument("--sort", default="updated_at")
    order = p_list.add_mutually_exclusive_group()
    order.add_argument("--desc", action="store_true")
    order.add_argument("--asc", action="store_true")

    p_show = sub.add_parser("show")
    p_show.add_argument("project_id")
    p_show.add_argument("task_id")
    p_show.add_argument("--body", action="store_true")
    p_show.add_argument("--max-body-chars", type=int)
    p_show.add_argument("--max-body-lines", type=int)

    p_move = sub.add_parser("move")
    p_move.add_argument("project_id")
    p_move.add_argument("task_id")
    p_move.add_argument("new_status")

    p_meta = sub.add_parser("meta-update")
    p_meta.add_argument("project_id")
    p_meta.add_argument("task_id")
    p_meta.add_argument("--patch-json")
    p_meta.add_argument("--patch-stdin", action="store_true")

    p_body = sub.add_parser("set-body")
    p_body.add_argument("project_id")
    p_body.add_argument("task_id")
    p_body.add_argument("--text")
    p_body.add_argument("--file")

    p_check = sub.add_parser("integrity-check")
    p_check.add_argument("project_id")
    p_check.add_argument("--fix", action="store_true")

    try:
        args = parser.parse_args(argv)
        cmd = args.command

        if cmd == "init-project":
            statuses = [s.strip() for s in args.statuses.split(",") if s.strip()]
            result = service.init_project(args.project_id, statuses)

        elif cmd == "add":
            result = service.add_task(
                args.project_id,
                task_id=args.task_id,
                status=args.status,
                body=args.body,
                tags=args.tags,
                assignee=args.assignee,
                priority=args.priority,
                due_date=args.due_date,
            )

        elif cmd == "list":
            desc = True
            if args.asc:
                desc = False
            elif args.desc:
                desc = True
            result = service.list_tasks(
                args.project_id,
                status=args.status,
                tag=args.tag,
                assignee=args.assignee,
                priority=args.priority,
                fields=args.fields,
                limit=args.limit,
                offset=args.offset,
                sort=args.sort,
                desc=desc,
            )

        elif cmd == "show":
            result = service.show_task(
                args.project_id,
                args.task_id,
                include_body=args.body,
                max_body_chars=args.max_body_chars,
                max_body_lines=args.max_body_lines,
            )

        elif cmd == "move":
            result = service.move_task(args.project_id, args.task_id, args.new_status)

        elif cmd == "meta-update":
            if bool(args.patch_json) == bool(args.patch_stdin):
                raise ValidationError("Provide exactly one of --patch-json or --patch-stdin")
            if args.patch_stdin:
                patch_raw = sys.stdin.read()
            else:
                patch_raw = args.patch_json
            try:
                patch = json.loads(patch_raw)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON patch")
            result = service.meta_update(args.project_id, args.task_id, patch)

        elif cmd == "set-body":
            result = service.set_body(args.project_id, args.task_id, text=args.text, file_path=args.file)

        elif cmd == "integrity-check":
            result = service.integrity_check(args.project_id, fix=args.fix)

        else:
            raise ValidationError("Unknown command")

        _print(result)
        return 0

    except TaskTrackingError as e:
        _print({"ok": False, "error": {"code": e.code, "message": e.message, "details": e.details}})
        return e.exit_code
    except Exception:
        _print({"ok": False, "error": {"code": "UNEXPECTED_ERROR", "message": "Unexpected error", "details": {}}})
        return 10


if __name__ == "__main__":
    sys.exit(main())
