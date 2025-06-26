SELECT pid, usename, datname, client_addr, state, query
FROM pg_stat_activity;

SELECT pg_terminate_backend(2180428);
SELECT pg_terminate_backend(2185261);
SELECT pg_terminate_backend(2182627);
SELECT pg_terminate_backend(2183090);
SELECT pg_terminate_backend(2185567);
SELECT pg_terminate_backend(2181111);
SELECT pg_terminate_backend(2181117);