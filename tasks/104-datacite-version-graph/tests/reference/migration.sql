INSERT INTO records(record_id,doi,kind,state,publication_date,cohort)
VALUES('REC-V4','10.data/cohort.v4','version','findable','2026-04-30','2026 pediatric cohort');

UPDATE edges SET from_doi='10.data/cohort', relation='HasVersion', to_doi='10.data/cohort.v2', status='corrected_direction', evidence_refs='relations.json#R3;prior_graph_state.json#datacite-v3-checkpoint' WHERE edge_id='R3';
INSERT INTO edges VALUES('R3-INVERSE','10.data/cohort.v2','IsVersionOf','10.data/cohort','corrected_direction','relations.json#R3;prior_graph_state.json#datacite-v3-checkpoint','relation');
UPDATE edges SET status='retained', evidence_refs='relations.json#R1;prior_graph_state.json#datacite-v3-checkpoint' WHERE edge_id='R1';
UPDATE edges SET status='retained', evidence_refs='relations.json#R2;prior_graph_state.json#datacite-v3-checkpoint' WHERE edge_id='R2';
UPDATE edges SET status='deduplicated', evidence_refs='relations.json#R4;relations.json#R5;prior_graph_state.json#datacite-v3-checkpoint' WHERE edge_id='R4';
DELETE FROM edges WHERE edge_id IN ('R5','R9','R10','C1-DUP');
UPDATE edges SET status='retained', evidence_refs='relations.json#R6;prior_graph_state.json#datacite-v3-checkpoint' WHERE edge_id='R6';
UPDATE edges SET status='retained', evidence_refs='relations.json#R7;prior_graph_state.json#datacite-v3-checkpoint' WHERE edge_id='R7';
UPDATE edges SET status='retained', evidence_refs='relations.json#R8;prior_graph_state.json#datacite-v3-checkpoint' WHERE edge_id='R8';
INSERT INTO edges VALUES('V1-PREV','10.data/cohort.v1','IsPreviousVersionOf','10.data/cohort.v2','added','records.json#REC-V1;records.json#REC-V2;prior_graph_state.json#datacite-v3-checkpoint','derived');
INSERT INTO edges VALUES('V2-NEW','10.data/cohort.v2','IsNewVersionOf','10.data/cohort.v1','added','records.json#REC-V1;records.json#REC-V2;prior_graph_state.json#datacite-v3-checkpoint','derived');
INSERT INTO edges VALUES('V4-HAS','10.data/cohort','HasVersion','10.data/cohort.v4','added','change.json#CH-2026-04;records.json#REC-V3','derived');
INSERT INTO edges VALUES('V4-IS','10.data/cohort.v4','IsVersionOf','10.data/cohort','added','change.json#CH-2026-04;records.json#REC-V3','derived');
INSERT INTO edges VALUES('V4-NEW','10.data/cohort.v4','IsNewVersionOf','10.data/cohort.v3','added','change.json#CH-2026-04;records.json#REC-V3','derived');
INSERT INTO edges VALUES('V3-PREV','10.data/cohort.v3','IsPreviousVersionOf','10.data/cohort.v4','added','change.json#CH-2026-04;records.json#REC-V3','derived');
UPDATE edges SET status='deduplicated', evidence_refs='citations.json#C1;citations.json#C1-DUP' WHERE edge_id='C1';
UPDATE edges SET to_doi='10.data/cohort.v4', status='retargeted', evidence_refs='citations.json#C2;change.json#CH-2026-04' WHERE edge_id='C2';
UPDATE edges SET status='preserved_concept_citation', evidence_refs='citations.json#C3;records.json#REC-CONCEPT' WHERE edge_id='C3';

INSERT INTO change_log VALUES('CL-01','add_version','change.json#CH-2026-04','','10.data/cohort.v4');
INSERT INTO change_log VALUES('CL-02','correct_direction','relations.json#R3','10.data/cohort.v2|HasVersion|10.data/cohort','10.data/cohort|HasVersion|10.data/cohort.v2');
INSERT INTO change_log VALUES('CL-03','remove_duplicate','relations.json#R5','R5','R4');
INSERT INTO change_log VALUES('CL-04','remove_self_edge','relations.json#R9','R9','');
INSERT INTO change_log VALUES('CL-05','remove_draft_edge','relations.json#R10','R10','');
INSERT INTO change_log VALUES('CL-06','remove_duplicate_citation','citations.json#C1-DUP','C1-DUP','C1');
INSERT INTO change_log VALUES('CL-07','retarget_citation','citations.json#C2','10.data/cohort.v3','10.data/cohort.v4');
