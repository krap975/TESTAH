"""Audit configuration without values. Optional OAuth only; never creates payments."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy.engine import make_url
from app.core.config import Settings
from app.database.session import build_engine, make_session_factory
from app.payments.configuration import authenticate_configuration, configuration_report
from app.payments.paypal import PayPalSandbox


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--authenticate", action="store_true", help="Validate OAuth credentials only; no payment requests.")
    args = parser.parse_args()
    if not args.env_file.is_file():
        print("Configuration file is missing; no requests or changes made.")
        return 1
    # A staged file must be the configuration actually checked. Never silently
    # authenticate process overrides instead of the locally supplied app.
    overrides = sorted(name for name in os.environ if name.startswith("TESTAH_"))
    if overrides:
        print(json.dumps({"process_override_names": overrides, "validation_blocked": True}))
        return 1
    engine = None
    try:
        settings = Settings(_env_file=args.env_file)
        url = make_url(settings.database_url)
        if url.get_backend_name() == "sqlite" and url.database not in (None, "", ":memory:"):
            database = Path(url.database)
            if not database.is_absolute():
                database = ROOT / database
            if not database.is_file():
                print("Existing database not found; no requests or changes made.")
                return 1
        engine = build_engine(settings.database_url)
        with make_session_factory(engine)() as session:
            if url.get_backend_name() == "sqlite":
                from sqlalchemy import text
                session.execute(text("PRAGMA query_only=ON"))
            report = configuration_report(session, settings)
        ready = report["configuration_present"] and report["sandbox_mode"] and report["sandbox_origin_fixed"]
        if args.authenticate and ready:
            report.update(asyncio.run(authenticate_configuration(PayPalSandbox(settings))))
        print(json.dumps(report, sort_keys=True))
        return 0 if ready and (not args.authenticate or report["oauth_authenticated"]) else 1
    except Exception:
        # Settings/DB/network internals may include credentials or private paths.
        print("Configuration preflight failed safely; no payment requests or configuration changes made.")
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
