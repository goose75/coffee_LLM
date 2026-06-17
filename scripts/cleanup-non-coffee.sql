-- Identify and remove non-coffee items from the database
-- Run this to see what will be deleted:
--   psql "$DATABASE_URL" -f scripts/cleanup-non-coffee.sql
--
-- The script uses pattern matching to identify:
-- - Subscriptions (weekly, monthly, seasonal plans)
-- - Bundles & gifts (gift sets, bundles, packages)
-- - Pods & capsules (Nespresso, K-Cups, etc.)
-- - Equipment (grinders, kettles, scales, brewers)
-- - Courses & classes (barista training, latte art)
-- - Merchandise (t-shirts, posters, stickers)
-- - Non-coffee beverages (tea, matcha, chocolate)
-- - Cups & mugs (vessels, tumblers)

-- Step 1: Identify non-coffee items
-- Shows what will be deleted without making changes

WITH non_coffee_patterns AS (
  SELECT
    cb.id,
    cb.canonical_name,
    CASE
      WHEN cb.canonical_name ~* 'subscription|(\b(weekly|monthly|fortnightly|quarterly)\s+(plan|box|delivery))|(\b(one|two|three|four|six|twelve)(-| )?month)'
        THEN 'subscription'
      WHEN cb.canonical_name ~* 'gift\s+(set|box|pack|card|message)|bundle'
        THEN 'bundles & gifts'
      WHEN cb.canonical_name ~* 'capsule|pod|nespresso'
        THEN 'pods & capsules'
      WHEN cb.canonical_name ~* 'grinder|kettle|scale|fellow|bialetti|chemex|aeropress|wilfa|hario|timemore'
        THEN 'equipment'
      WHEN cb.canonical_name ~* 'course|class|workshop|barista'
        THEN 'courses & classes'
      WHEN cb.canonical_name ~* 'poster|print|t-?shirt|sticker|apron|hat'
        THEN 'merchandise'
      WHEN cb.canonical_name ~* 'matcha|tea|chocolate|chai'
        THEN 'non-coffee beverages'
      WHEN cb.canonical_name ~* '\b(cup|mug|tumbler|glass|vessel)\b'
        THEN 'cups & mugs'
      ELSE 'other'
    END AS category
  FROM canonical_beans cb
  WHERE cb.canonical_name ~* 'subscription|(\b(weekly|monthly|fortnightly|quarterly)\s+(plan|box|delivery))|(\b(one|two|three|four|six|twelve)(-| )?month)|gift\s+(set|box|pack|card|message)|bundle|capsule|pod|nespresso|grinder|kettle|scale|fellow|bialetti|chemex|aeropress|wilfa|hario|timemore|course|class|workshop|barista|poster|print|t-?shirt|sticker|apron|hat|matcha|tea|chocolate|chai|\b(cup|mug|tumbler|glass|vessel)\b'
)
SELECT
  category,
  COUNT(*) as count,
  string_agg(canonical_name, E'\n  - ' ORDER BY canonical_name) as examples
FROM non_coffee_patterns
GROUP BY category
ORDER BY count DESC;

-- Step 2: Summary stats
-- Uncomment the section below to see the deletion summary

/*
WITH non_coffee_ids AS (
  SELECT cb.id
  FROM canonical_beans cb
  WHERE cb.canonical_name ~* 'subscription|(\b(weekly|monthly|fortnightly|quarterly)\s+(plan|box|delivery))|(\b(one|two|three|four|six|twelve)(-| )?month)|gift\s+(set|box|pack|card|message)|bundle|capsule|pod|nespresso|grinder|kettle|scale|fellow|bialetti|chemex|aeropress|wilfa|hario|timemore|course|class|workshop|barista|poster|print|t-?shirt|sticker|apron|hat|matcha|tea|chocolate|chai|\b(cup|mug|tumbler|glass|vessel)\b'
)
SELECT
  'Canonical beans to delete' as item,
  COUNT(*) as count
FROM non_coffee_ids
UNION ALL
SELECT 'Bean listings to delete', COUNT(*) FROM bean_listings WHERE canonical_bean_id IN (SELECT id FROM non_coffee_ids)
UNION ALL
SELECT 'Listing variants to delete', COUNT(*) FROM listing_variants WHERE bean_listing_id IN (SELECT id FROM bean_listings WHERE canonical_bean_id IN (SELECT id FROM non_coffee_ids));
*/
