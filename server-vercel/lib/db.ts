import mysql from 'mysql2/promise';

let pool: mysql.Pool | null = null;

export function getPool(): mysql.Pool {
  if (!pool) {
    const host = process.env.DB_HOST || 'localhost';
    const user = process.env.DB_USER || 'ashifash_auth';
    const password = process.env.DB_PASSWORD || 'AuthDbPass@2026!#Mega';
    const database = process.env.DB_NAME || 'ashifash_auth';
    const port = parseInt(process.env.DB_PORT || '3306', 10);

    pool = mysql.createPool({
      host,
      user,
      password,
      database,
      port,
      waitForConnections: true,
      connectionLimit: 10,
      queueLimit: 0,
      multipleStatements: true,
      enableKeepAlive: true,
      keepAliveInitialDelay: 10000,
      timezone: 'Z',
      dateStrings: true,
    });
  }
  return pool;
}

function transformSql(text: string, params: any[]): { sql: string; params: any[] } {
  if (!params || params.length === 0) {
    let sql = text.replace(/\bILIKE\b/gi, 'LIKE');
    sql = sql.replace(/INTERVAL\s+'(\d+)\s*([a-zA-Z]+)'/gi, (_, val, unit) => {
      const u = unit.toUpperCase().replace(/S$/, '');
      return `INTERVAL ${val} ${u}`;
    });
    return { sql, params: [] };
  }

  const mysqlParams: any[] = [];

  // Map $1, $2, ... placeholders to ? and map corresponding parameters in order
  let sql = text.replace(/\$(\d+)/g, (fullMatch, numStr) => {
    const idx = parseInt(numStr, 10) - 1;
    if (idx >= 0 && idx < params.length) {
      mysqlParams.push(params[idx]);
      return '?';
    }
    return fullMatch;
  });

  const finalParams = mysqlParams.length > 0 ? mysqlParams : params;

  // Map PostgreSQL ILIKE to MySQL LIKE
  sql = sql.replace(/\bILIKE\b/gi, 'LIKE');

  // Map PostgreSQL INTERVAL 'x unit' -> INTERVAL x unit
  sql = sql.replace(/INTERVAL\s+'(\d+)\s*([a-zA-Z]+)'/gi, (_, val, unit) => {
    const u = unit.toUpperCase().replace(/S$/, '');
    return `INTERVAL ${val} ${u}`;
  });

  return { sql, params: finalParams };
}

export async function query<T = any>(
  text: string,
  params: any[] = []
): Promise<{ rows: T[]; rowCount: number }> {
  const p = getPool();
  const { sql, params: finalParams } = transformSql(text, params);

  const [rawResult] = await p.query(sql, finalParams);

  let rows: T[] = [];
  let rowCount = 0;

  if (Array.isArray(rawResult)) {
    rows = rawResult as T[];
    rowCount = rows.length;
    for (const row of rows) {
      if (row && typeof row === 'object') {
        if ((row as any)['COUNT(*)'] !== undefined && (row as any).count === undefined) {
          (row as any).count = (row as any)['COUNT(*)'];
        }
      }
    }
  } else if (rawResult && typeof rawResult === 'object') {
    const header = rawResult as any;
    rowCount = header.affectedRows ?? 0;
    if (header.insertId) {
      rows = [{ id: header.insertId } as any];
    }
  }

  return {
    rows,
    rowCount,
  };
}
