"""
SELECT-only verification script.
Checks that saved MCQs have proper learning_item and taxonomy links in App Dev.
"""
import psycopg2
import psycopg2.extras

APP_DEV_CONFIG = {
    "host": "13.203.24.116",
    "port": "6001",
    "database": "prayas",
    "user": "developer_prayas_user",
    "password": "prayas_ai_2025",
}

conn = psycopg2.connect(**APP_DEV_CONFIG)
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

print("=" * 70)
print("1. MCQs with no learning_item link (learningItemId IS NULL)")
print("=" * 70)
cur.execute("""
    SELECT id, "questionText"
    FROM mcqs
    WHERE "learningItemId" IS NULL
    LIMIT 20
""")
rows = cur.fetchall()
print(f"Found: {len(rows)}")
for r in rows:
    print(f"  {r['id']} | {r['questionText'][:80]}")

print()
print("=" * 70)
print("2. MCQs whose learningItemId doesn't exist in learning_items (orphaned)")
print("=" * 70)
cur.execute("""
    SELECT m.id, m."questionText"
    FROM mcqs m
    LEFT JOIN learning_items li ON li.id = m."learningItemId"
    WHERE li.id IS NULL
    LIMIT 20
""")
rows = cur.fetchall()
print(f"Found: {len(rows)}")
for r in rows:
    print(f"  {r['id']} | {r['questionText'][:80]}")

print()
print("=" * 70)
print("3. MCQs with no taxonomy links (learning_item_taxonomies empty)")
print("=" * 70)
cur.execute("""
    SELECT m.id, m."questionText", li.id as li_id
    FROM mcqs m
    JOIN learning_items li ON li.id = m."learningItemId"
    LEFT JOIN learning_item_taxonomies lit ON lit."learningItemId" = li.id
    WHERE lit.id IS NULL
    LIMIT 20
""")
rows = cur.fetchall()
print(f"Found: {len(rows)}")
for r in rows:
    print(f"  mcq={r['id']} | li={r['li_id']} | {r['questionText'][:70]}")

print()
print("=" * 70)
print("4. Sample of well-formed MCQs (has li + taxonomy)")
print("=" * 70)
cur.execute("""
    SELECT m.id, m."questionText",
           li.id as li_id, li."difficultyLevel", li.tags,
           array_agg(t.name ORDER BY t.level) as taxonomy_chain
    FROM mcqs m
    JOIN learning_items li ON li.id = m."learningItemId"
    JOIN learning_item_taxonomies lit ON lit."learningItemId" = li.id
    JOIN taxonomies t ON t.id = lit."taxonomyId"
    GROUP BY m.id, m."questionText", li.id, li."difficultyLevel", li.tags
    LIMIT 10
""")
rows = cur.fetchall()
print(f"Found: {len(rows)}")
for r in rows:
    print(f"  mcq={str(r['id'])[:8]}... | difficulty={r['difficultyLevel']} | tags={r['tags']} | taxonomy={r['taxonomy_chain']}")
    print(f"    Q: {r['questionText'][:80]}")

print()
print("=" * 70)
print("5. Orphaned learning_items (no mcq pointing to them)")
print("=" * 70)
cur.execute("""
    SELECT li.id, li."createdAt"
    FROM learning_items li
    LEFT JOIN mcqs m ON m."learningItemId" = li.id
    WHERE m.id IS NULL
    ORDER BY li."createdAt" DESC
    LIMIT 20
""")
rows = cur.fetchall()
print(f"Found: {len(rows)}")
for r in rows:
    print(f"  li={r['id']} | created={r['createdAt']}")

print()
print("=" * 70)
print("6. Taxonomy table — available levels and names (first 30)")
print("=" * 70)
cur.execute("""
    SELECT level, name FROM taxonomies ORDER BY level, name LIMIT 30
""")
rows = cur.fetchall()
for r in rows:
    print(f"  level={r['level']} | {r['name']}")

cur.close()
conn.close()
print("\nDone.")
