-- Delete non-coffee items from the database
-- This script identifies and removes products that are not roasted coffee beans
--
-- Categories removed:
-- - Subscriptions (weekly/monthly plans, seasonal boxes)
-- - Bundles & gifts (gift sets, bundles, packages)
-- - Pods & capsules (Nespresso, K-Cups, etc.)
-- - Equipment (grinders, kettles, scales, brewers)
-- - Courses & classes (barista training, latte art)
-- - Merchandise (t-shirts, posters, stickers, etc.)
-- - Non-coffee beverages (tea, matcha, chocolate, chai)
-- - Cups & mugs (vessels, tumblers, glassware)

BEGIN;

-- STEP 1: Identify non-coffee canonical beans using CTE
-- Pattern matches common non-coffee product names
CREATE TEMPORARY TABLE non_coffee_ids AS
SELECT cb.id
FROM canonical_beans cb
WHERE cb.canonical_name ~* (
  'subscription|' ||
  '(\b(weekly|monthly|fortnightly|quarterly)\s+(plan|box|delivery))|' ||
  '(\b(one|two|three|four|six|twelve)[\s-]*month\b)|' ||
  'gift\s+(set|box|pack|card|message)|' ||
  'bundle|' ||
  'capsule|pod|nespresso|' ||
  'grinder|kettle|scale|bialetti|chemex|aeropress|wilfa|hario|timemore|commandante|fellow|bodum|wacaco|picopresso|flair|' ||
  'course|class|workshop|barista|' ||
  'poster|print|t-?shirt|sticker|apron|hat|' ||
  'matcha|tea|chocolate|chai|' ||
  '\b(cup|mug|tumbler|glass|vessel)\b'
);

-- STEP 2: Delete in dependency order
-- Delete canonical matches that reference non-coffee beans
DELETE FROM canonical_matches
WHERE proposed_canonical_bean_id IN (SELECT id FROM non_coffee_ids)
   OR bean_listing_id IN (
     SELECT id FROM bean_listings
     WHERE canonical_bean_id IN (SELECT id FROM non_coffee_ids)
   );

-- Delete flavour tags
DELETE FROM bean_flavour_tags
WHERE bean_id IN (SELECT id FROM non_coffee_ids);

-- Delete price history records
DELETE FROM price_history
WHERE listing_variant_id IN (
  SELECT id FROM listing_variants
  WHERE bean_listing_id IN (
    SELECT id FROM bean_listings
    WHERE canonical_bean_id IN (SELECT id FROM non_coffee_ids)
  )
);

-- Delete listing variants
DELETE FROM listing_variants
WHERE bean_listing_id IN (
  SELECT id FROM bean_listings
  WHERE canonical_bean_id IN (SELECT id FROM non_coffee_ids)
);

-- Delete bean listings
DELETE FROM bean_listings
WHERE canonical_bean_id IN (SELECT id FROM non_coffee_ids);

-- Delete the canonical beans themselves
DELETE FROM canonical_beans
WHERE id IN (SELECT id FROM non_coffee_ids);

-- Clean up temp table
DROP TABLE non_coffee_ids;

COMMIT;

-- Report results
SELECT
  'Cleanup complete' as status,
  (SELECT COUNT(*) FROM canonical_beans) as canonical_beans_remaining,
  (SELECT COUNT(*) FROM bean_listings) as bean_listings_remaining,
  (SELECT COUNT(*) FROM listing_variants) as listing_variants_remaining;
