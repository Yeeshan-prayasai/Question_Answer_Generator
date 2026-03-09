import psycopg2, psycopg2.extras, re, tomllib, os

secrets_path = os.path.join(os.path.dirname(__file__), '.streamlit', 'secrets.toml')
with open(secrets_path, 'rb') as f:
    secrets = tomllib.load(f)

conn = psycopg2.connect(
    host=secrets['host'], database=secrets['database'],
    user=secrets['user'], password=secrets['password'], port=secrets['port']
)
cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
cur.execute('SELECT id, question_english, answer, explanation FROM upsc_prelims_ai_generated_que WHERE explanation IS NOT NULL')
rows = cur.fetchall()
conn.close()

mismatches = []
no_ca_found = []

for row in rows:
    exp = row['explanation'] or ''
    db_answer = (row['answer'] or '').strip().upper().strip('()')

    match = re.search(r'Correct Answer\s*:\s*\(?([A-Da-d])\)?', exp, re.IGNORECASE)
    if not match:
        no_ca_found.append((row['id'], exp.strip()[:120]))
        continue

    exp_answer = match.group(1).upper()
    if exp_answer != db_answer:
        mismatches.append({
            'id': row['id'],
            'db_answer': db_answer,
            'exp_answer': exp_answer,
            'question': row['question_english'][:120],
            'exp_first_line': exp.strip().splitlines()[0][:80],
        })

print(f'Total checked: {len(rows)}')
print(f'No Correct Answer line found: {len(no_ca_found)}')
print(f'Mismatches (exp answer != db answer): {len(mismatches)}')

if no_ca_found:
    print('\n--- No Correct Answer found ---')
    for uid, preview in no_ca_found:
        print(f'  {uid}')
        print(f'  Preview: {preview}')
        print()

if mismatches:
    print('\n--- Mismatches ---')
    for m in mismatches:
        print(f'  ID:       {m["id"]}')
        print(f'  DB ans:   {m["db_answer"]}  |  Exp says: {m["exp_answer"]}')
        print(f'  Question: {m["question"]}')
        print(f'  Exp line: {m["exp_first_line"]}')
        print()
