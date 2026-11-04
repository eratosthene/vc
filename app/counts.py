"""The counts on the index page and on the Print View's index page."""

from sqlalchemy import func

from app import db


def collection_counts():
    """
    The number of items in the collection, per folder, per category and per
    decade of the master's year, and the number in folders that count as LPs.
    The folders and categories are in name order, the decades oldest first.
    """
    from app.models import Category, CollectionItem, Folder

    full_total = db.session.query(CollectionItem).count()
    lp_total = 0
    by_folder = []
    by_category = []
    by_decade = []
    for f in db.session.query(Folder).order_by(Folder.name):
        c = db.session.query(CollectionItem).filter_by(folder_id=f.id).count()
        by_folder.append({"folder": f, "total": c})
        if f.counts_as_lp:
            lp_total += c
    for f in db.session.query(Category).order_by(Category.name):
        c = (
            db.session.query(CollectionItem)
            .filter(CollectionItem.categories.any(Category.id == f.id))
            .count()
        )
        by_category.append({"category": f, "total": c})
    decade = func.floor(CollectionItem.master_year / 10) * 10
    dc = (
        db.session.query(decade, func.count())
        .filter(CollectionItem.master_year > 0)
        .group_by(decade)
        .order_by(decade)
    )
    for d, count in dc:
        decade = str(int(d)) + "s"
        by_decade.append(
            {
                "decade": decade,
                "count": count,
                "before": int(decade[:-1]) + 10,
                "after": int(decade[:-1]) - 1,
            }
        )
    return {
        "lp_total": lp_total,
        "full_total": full_total,
        "by_folder": by_folder,
        "by_category": by_category,
        "by_decade": by_decade,
    }
