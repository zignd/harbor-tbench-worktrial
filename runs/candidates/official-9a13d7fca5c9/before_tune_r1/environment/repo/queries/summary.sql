SELECT id,status,amount FROM events WHERE status ILIKE $needle ORDER BY id;
