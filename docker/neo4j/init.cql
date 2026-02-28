CREATE CONSTRAINT node_id_unique IF NOT EXISTS FOR (n:Entity) REQUIRE n.node_id IS UNIQUE;
CREATE INDEX entity_type_idx IF NOT EXISTS FOR (n:Entity) ON (n.node_type);
