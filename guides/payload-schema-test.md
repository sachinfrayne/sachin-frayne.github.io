# Payload schema test: what Qdrant does with mistyped and undeclared fields

This test shows how Qdrant handles payload fields that are not declared in the schema, or that have the wrong type. Run it in the Qdrant Cloud dev tools console on a throwaway collection, then delete the collection.

The short version: Qdrant does not guess types, and it does not reject bad values. It stores what you send, and filters quietly skip values that do not match the field's type.

## What you need

- A Qdrant Cloud cluster.
- A text embedding model from the **Inference** tab of your cluster. Copy its model name and its vector size.
- The dev tools console, open in the Qdrant Cloud console.

Before you run the requests, replace every `<model from the Inference tab>` with your model name, and set `size` in step 1 to your model's vector size. The examples use `384`.

Run the requests in order, one at a time. Each request has a line with the HTTP method and path, then the JSON body.

## Step 1: Create a test collection

```http
PUT /collections/schema_test
{
  "vectors": {
    "size": 384,
    "distance": "Cosine"
  }
}
```

## Step 2: Declare three indexes

Declare these indexes, but leave `rating` undeclared on purpose. Run each request separately.

```http
PUT /collections/schema_test/index
{ "field_name": "cuisine", "field_schema": "keyword" }
```

```http
PUT /collections/schema_test/index
{ "field_name": "minutes", "field_schema": "integer" }
```

```http
PUT /collections/schema_test/index
{ "field_name": "added_on", "field_schema": "datetime" }
```

## Step 3: Load four recipes with mistakes on purpose

Each recipe has a different problem:

- ID 1 is correct.
- ID 2 has `minutes` as the string `"20"`, not the number `20`.
- ID 3 has an `added_on` value of `"last tuesday"`, which is not a date.
- ID 4 has a field, `spice_level`, that was never declared in the schema.

```http
PUT /collections/schema_test/points?wait=true
{
  "points": [
    {
      "id": 1,
      "vector": { "text": "Green curry with crispy tofu, lime, and basil", "model": "<model from the Inference tab>" },
      "payload": { "title": "Green Curry with Tofu", "cuisine": "thai", "minutes": 25, "added_on": "2026-10-03", "rating": 4.5 }
    },
    {
      "id": 2,
      "vector": { "text": "Red lentil soup with cumin and lemon", "model": "<model from the Inference tab>" },
      "payload": { "title": "Lentil Soup", "cuisine": "indian", "minutes": "20", "added_on": "2026-10-04", "rating": 3.0 }
    },
    {
      "id": 3,
      "vector": { "text": "Wide rice noodles fried with egg and greens", "model": "<model from the Inference tab>" },
      "payload": { "title": "Pad See Ew", "cuisine": "thai", "minutes": 30, "added_on": "last tuesday", "rating": 4.8 }
    },
    {
      "id": 4,
      "vector": { "text": "Quick tofu and vegetable stir fry with chili", "model": "<model from the Inference tab>" },
      "payload": { "title": "Mystery Dish", "cuisine": "thai", "minutes": 10, "added_on": "2026-10-05", "rating": 4.2, "spice_level": 3 }
    }
  ]
}
```

The write succeeds for all four points. Qdrant does not report the mistakes.

## Step 4: Run the filters

Run each of these searches. The comment above each one says what you should see.

```http
POST /collections/schema_test/points/scroll
{ "filter": { "must": [ { "key": "cuisine", "match": { "value": "thai" } } ] }, "limit": 10 }
```

Expected IDs: **1, 3, 4**. The keyword index works.

```http
POST /collections/schema_test/points/scroll
{ "filter": { "must": [ { "key": "minutes", "range": { "lt": 30 } } ] }, "limit": 10 }
```

Expected IDs: **1, 4**. ID 2 is skipped because `"20"` is a string, even though `minutes` has an integer index.

```http
POST /collections/schema_test/points/scroll
{ "filter": { "must": [ { "key": "minutes", "match": { "value": "20" } } ] }, "limit": 10 }
```

Expected IDs: **2**. An exact match on the string finds it, which shows the value was stored as text.

```http
POST /collections/schema_test/points/scroll
{ "filter": { "must": [ { "key": "added_on", "range": { "gte": "2026-10-01T00:00:00Z" } } ] }, "limit": 10 }
```

Expected IDs: **1, 2, 4**. ID 3 is skipped because `"last tuesday"` is not a date.

```http
POST /collections/schema_test/points/scroll
{ "filter": { "must": [ { "key": "rating", "range": { "gte": 4 } } ] }, "limit": 10 }
```

Expected IDs: **1, 3, 4**. `rating` was never declared as an index, but the filter still works. Qdrant scans for it, which is slower on large data.

```http
POST /collections/schema_test/points/scroll
{ "filter": { "must": [ { "key": "spice_level", "range": { "gte": 1 } } ] }, "limit": 10 }
```

Expected IDs: **4**. An undeclared field still filters.

## Step 5: Check the indexed counts

This shows how many points hold each indexed field. Compare the counts with the total points.

```http
GET /collections/schema_test
```

Look at `payload_schema` in the response. Expected:

- `minutes` with `"data_type": "integer"` and `"points": 3`. Four points were loaded, so one value (ID 2) was not indexed as an integer.
- `added_on` with `"data_type": "datetime"` and `"points": 3`. The bad date on ID 3 was not indexed.
- `cuisine` with `"data_type": "keyword"` and `"points": 4`.

`rating` and `spice_level` do not appear, because they have no index.

## Step 6: Clean up

```http
DELETE /collections/schema_test
```

## What to take away

- An undeclared field still works in filters. It is slower, but nothing fails.
- A value with the wrong type is stored, but range filters skip it. Check your data before you load it.
- A bad date is stored the same way. Only a datetime filter reveals it.
- Qdrant reports neither problem on write. The per-field `points` counts in the collection info are how you catch them.
