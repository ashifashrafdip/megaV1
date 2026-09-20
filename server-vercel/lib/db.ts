import { Pool } from '@neondatabase/serverless';
import fs from 'fs';
import path from 'path';

let pool: any = null;
let memDbPool: any = null;

const DEFAULT_NEON_URL =
  'postgresql://neondb_owner:npg_Y3hiK4JNXqsx@ep-quiet-darkness-auh729zw-pooler.c-10.us-east-1.aws.neon.tech/neondb?channel_binding=require&sslmode=require';


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
    const connectionString =
      process.env.DATABASE_URL ||
      process.env.POSTGRES_URL ||
      process.env.DATABASE_URL_UNPOOLED ||
      process.env.POSTGRES_PRISMA_URL ||
      DEFAULT_NEON_URL;

    if (connectionString === 'memory') {
      console.log('ℹ️  Using in-memory PostgreSQL emulator.');
      pool = getMemDbPool();
      return pool;
    }

    try {
      pool = new Pool({ connectionString });
    } catch (err) {
      console.error('Failed to initialize Neon pool, falling back to in-memory:', err);
      pool = getMemDbPool();
    }
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
