import { Pool } from '@neondatabase/serverless';
import fs from 'fs';
import path from 'path';

let pool: any = null;
let memDbPool: any = null;

function getMemDbPool() {
  if (!memDbPool) {
    const { newDb } = require('pg-mem');
    const db = newDb();

    // Load and execute schema.sql
    const schemaPath = path.join(process.cwd(), 'schema.sql');
    if (fs.existsSync(schemaPath)) {
      const sql = fs.readFileSync(schemaPath, 'utf-8');
      db.public.none(sql);
    }
    const pg = db.adapters.createPg();
    memDbPool = new pg.Pool();
  }
  return memDbPool;
}

export function getPool() {
  if (!pool) {
    const connectionString = process.env.DATABASE_URL;
    if (!connectionString || connectionString === 'memory' || !connectionString.startsWith('postgres')) {
      console.log('ℹ️  Using in-memory PostgreSQL emulator (Set DATABASE_URL in .env to connect to Neon).');
      pool = getMemDbPool();
      return pool;
    }
    pool = new Pool({ connectionString });
  }
  return pool;
}

export async function query<T = any>(
  text: string,
  params: any[] = []
): Promise<{ rows: T[]; rowCount: number }> {
  const p = getPool();
  const res = await p.query(text, params);
  return {
    rows: (res.rows || []) as T[],
    rowCount: res.rowCount ?? (res.rows ? res.rows.length : 0),
  };
}
