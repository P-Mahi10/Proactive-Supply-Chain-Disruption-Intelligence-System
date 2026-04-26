import pkg from 'pg';
import dotenv from 'dotenv';
dotenv.config();

const { Pool } = pkg;
const pool = new Pool({
  connectionString: process.env.DATABASE_URL
});

const query = `
  SELECT r.origin, r.destination, tm.name as route, rm.cost_per_unit as cost, rm.estimated_time_hours as delay_factor
  FROM route_metrics rm
  JOIN route_options ro ON rm.route_option_id = ro.id
  JOIN routes r ON ro.route_id = r.id
  JOIN transport_modes tm ON ro.transport_mode_id = tm.id
  WHERE rm.condition_type = 'current'
  ORDER BY rm.cost_per_unit ASC
  LIMIT 4;
`;

pool.query(query)
  .then(res => {
    console.log(JSON.stringify(res.rows, null, 2));
    process.exit(0);
  })
  .catch(err => {
    console.error(err);
    process.exit(1);
  });
