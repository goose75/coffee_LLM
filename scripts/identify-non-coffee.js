#!/usr/bin/env node
/**
 * Identify non-coffee items in the database
 * Usage: node scripts/identify-non-coffee.js
 */
const { Pool } = require('pg');

const EXCLUDE_PATTERNS = [
  // Subscriptions
  /\bsubscription\b/i,
  /\b(?:weekly|monthly|fortnightly|quarterly)\s+(?:plan|box|delivery)\b/i,
  /\b(?:one|two|three|four|six|twelve)[\s-]*month\b/i,

  // Gift sets, bundles
  /\bgift\s*(set|box|pack|card|message)\b/i,
  /\bbundle\b/i,

  // Capsules/pods
  /\bcapsule[s]?\b/i,
  /\bpod[s]?\b/i,
  /\bnespresso\b/i,

  // Equipment
  /\bgrinder\b/i,
  /\bkettle\b/i,
  /\bscale[s]?\b/i,
  /\bfellow\b/i,
  /\bbialetti\b/i,
  /\bchemex\b/i,
  /\baeropress\b/i,
  /\bwilfa\b/i,
  /\bhario\b/i,

  // Courses/classes
  /\bcourse\b/i,
  /\bclass\b/i,
  /\bworkshop\b/i,
  /\bbarista\s+(?:class|course|training)\b/i,

  // Merchandise
  /\bposter\b/i,
  /\bprint\b/i,
  /\bt-?shirt\b/i,
  /\bsticker\b/i,
  /\bapron\b/i,

  // Non-coffee beverages
  /\bmatcha\b/i,
  /\bdrinking\s+chocolate\b/i,
  /\btea[s]?\b/i,

  // Cups, mugs, vessels
  /\b(?:cup|mug|tumbler|glass|vessel)\b/i,

  // Misc
  /\bcertification\b/i,
  /\bsample\s+pack\b/i,
];

const CATEGORIES = {
  'subscription': /subscription|\bmonth\b/i,
  'bundles & gifts': /\bgift\b|\bbundle\b/i,
  'pods & capsules': /\b(?:capsule|pod)\b|\bnespresso\b/i,
  'equipment': /grinder|kettle|scale|fellow|bialetti|chemex|aeropress|wilfa|hario/i,
  'courses': /course|class|workshop|barista/i,
  'merchandise': /poster|print|t-?shirt|sticker|apron/i,
  'other beverages': /matcha|tea|chocolate/i,
  'cups & mugs': /\b(?:cup|mug|tumbler|glass)\b/i,
  'other': /^/,
};

async function main() {
  const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
  });

  try {
    const result = await pool.query(`
      SELECT id, canonical_name
      FROM canonical_beans
      ORDER BY canonical_name
    `);

    const beans = result.rows;
    console.log(`Total canonical beans: ${beans.length}\n`);

    const nonCoffee = [];
    const byCategory = {};

    for (const { id, canonical_name } of beans) {
      const nameUpper = canonical_name.toUpperCase();
      let matched = false;

      for (const pattern of EXCLUDE_PATTERNS) {
        if (pattern.test(canonical_name)) {
          nonCoffee.push({ id, name: canonical_name });

          // Categorize
          for (const [category, categoryPattern] of Object.entries(CATEGORIES)) {
            if (categoryPattern.test(canonical_name)) {
              if (!byCategory[category]) byCategory[category] = [];
              byCategory[category].push(canonical_name);
              break;
            }
          }

          matched = true;
          break;
        }
      }
    }

    console.log('='.repeat(80));
    console.log('NON-COFFEE ITEMS FOUND');
    console.log('='.repeat(80));

    for (const category of Object.keys(byCategory).sort()) {
      const items = byCategory[category];
      console.log(`\n${category.toUpperCase()}: ${items.length} items`);
      console.log('-'.repeat(80));

      items.slice(0, 15).forEach(item => {
        console.log(`  ✗ ${item}`);
      });

      if (items.length > 15) {
        console.log(`  ... and ${items.length - 15} more`);
      }
    }

    console.log(`\n${'='.repeat(80)}`);
    console.log(`Total non-coffee items: ${nonCoffee.length}`);
    console.log(`Percentage to remove: ${(nonCoffee.length / beans.length * 100).toFixed(1)}%`);
    console.log(`${'='.repeat(80)}\n`);

    // Output IDs for deletion
    if (nonCoffee.length > 0) {
      console.log('IDs to delete:');
      console.log(nonCoffee.map(item => `'${item.id}'`).join(', '));
    }

  } catch (error) {
    console.error('Error:', error.message);
    process.exit(1);
  } finally {
    await pool.end();
  }
}

main();
