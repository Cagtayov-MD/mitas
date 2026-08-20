-- McGrady kulesi — CreditKB sabit sorguları (salt-okunur).
-- Tüm kullanıcı verisi ? parametresiyle bağlanır; bu dosyada değişken KURULUM yoktur.
-- Biçim: "-- @ad:" satırı ile başlayan blok, adının karşılığı olan sorgudur.
-- tr_fold makrosu credit_crosscheck.py'de bağlantı başında TEMP MACRO olarak kurulur.

-- @wd_exact_label_tr:
SELECT qid,name,label_tr,publication_year,director,cast_member,imdb_id,tmdb_movie_id FROM works_master WHERE tr_fold(label_tr)=? LIMIT 60

-- @wd_exact_label_en:
SELECT qid,name,label_tr,publication_year,director,cast_member,imdb_id,tmdb_movie_id FROM works_master WHERE tr_fold(label_en)=? LIMIT 60

-- @wd_exact_name:
SELECT qid,name,label_tr,publication_year,director,cast_member,imdb_id,tmdb_movie_id FROM works_master WHERE tr_fold(name)=? LIMIT 60

-- @wd_like_label_tr:
SELECT qid,name,label_tr,publication_year,director,cast_member,imdb_id,tmdb_movie_id FROM works_master WHERE tr_fold(label_tr) LIKE ? LIMIT 60

-- @wd_like_label_en:
SELECT qid,name,label_tr,publication_year,director,cast_member,imdb_id,tmdb_movie_id FROM works_master WHERE tr_fold(label_en) LIKE ? LIMIT 60

-- @wd_like_name:
SELECT qid,name,label_tr,publication_year,director,cast_member,imdb_id,tmdb_movie_id FROM works_master WHERE tr_fold(name) LIKE ? LIMIT 60

-- @wd_qid_labels:
SELECT label_tr, label_en FROM qid_labels WHERE qid=?

-- @imdb_akas_exact:
SELECT DISTINCT tconst FROM akas WHERE tr_fold(title)=? LIMIT 20

-- @imdb_akas_like:
SELECT DISTINCT tconst FROM akas WHERE tr_fold(title) LIKE ? LIMIT 20

-- @imdb_titles_orig:
SELECT tconst FROM titles WHERE (originalTitle ILIKE ? OR primaryTitle ILIKE ?) AND titleType IN ('movie','tvMovie','tvSeries','tvMiniSeries') LIMIT 20

-- @imdb_titles_by_tconst:
SELECT primaryTitle,originalTitle,startYear FROM titles WHERE tconst=?

-- @imdb_titles_full:
SELECT primaryTitle,originalTitle,startYear,titleType FROM titles WHERE tconst=?

-- @imdb_names_primary:
SELECT primaryName FROM names WHERE nconst=?

-- @imdb_crew_directors:
SELECT directors FROM crew WHERE tconst=?

-- @imdb_principals_cast:
SELECT nconst FROM principals WHERE tconst=? AND category IN ('actor','actress') ORDER BY ordering LIMIT 10

-- @imdb_names_in_strip:
SELECT nconst FROM names WHERE list_contains(?, trim(regexp_replace(lower(strip_accents(primaryName)),'[^a-z0-9]+',' ','g')))

-- @imdb_names_in_plain:
SELECT nconst FROM names WHERE list_contains(?, trim(regexp_replace(lower(primaryName),'[^a-z0-9]+',' ','g')))

-- @imdb_principals_overlap:
SELECT tconst, count(DISTINCT nconst) c FROM principals WHERE list_contains(?, nconst) GROUP BY tconst HAVING count(DISTINCT nconst) >= 2 ORDER BY c DESC LIMIT 8
