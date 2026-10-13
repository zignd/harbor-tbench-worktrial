SELECT modality,stream,count(*) FROM normalized_events GROUP BY modality,stream;
