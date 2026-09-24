"""Opt-in local example quantities. Never replace real confirmed inventory."""
import argparse
from src.storage import ScanStore
from src.catalog import CatalogStore
from src.alternatives import AlternativeStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['seed-demo','seed-alternatives-demo'])
    parser.add_argument('--database')
    parser.add_argument('--scans')
    args = parser.parse_args()
    store = ScanStore(args.database,args.scans)
    try:
        store.initialize()
        if args.command == 'seed-demo':
            CatalogStore(store).seed_demo()
            print('Demo quantities seeded only where missing. These are examples, not observed availability.')
        else:
            AlternativeStore(CatalogStore(store)).seed_demo()
            print('Two demo Valser relationships seeded only where missing. No equivalence or dietary claims.')
    finally:
        store.close()


if __name__=='__main__':
    main()
