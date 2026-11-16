# Recipe search in Qdrant Cloud

This guide walks through the recipe search from the blog post, step by step, in the Qdrant Cloud dev tools console. You send text, and Qdrant creates the vectors inside your cluster. You do not run any embedding code on your machine.

## What you need

- A Qdrant Cloud cluster, with Cloud Inference enabled. A free cluster works.
- A text embedding model from the **Inference** tab of your cluster in the Qdrant Cloud console. Copy its model name and its vector size (dimensions).
- The dev tools console for your cluster, open in the Qdrant Cloud console.

## How to use the console

Each request in this guide has two parts: a line with the HTTP method and path, then the JSON body. Paste one request at a time into the console and run it.

Before you run the requests, replace every `<model from the Inference tab>` with the model name you copied, and make sure the `size` in step 1 matches that model's vector size. The examples use `384`.

## Step 1: Create the collection

A collection holds the vectors and payloads for one set of data. Its size and distance are fixed when you create it.

```http
PUT /collections/recipes
{
  "vectors": {
    "size": 384,
    "distance": "Cosine"
  },
  "quantization_config": {
    "turbo": {
      "bits": "bits4"
    }
  },
  "strict_mode_config": {
    "enabled": true,
    "unindexed_filtering_retrieve": false
  }
}
```

Strict mode rejects any search that filters on a field without an index. That keeps the guide's filters honest: if you filter on a field you forgot to index, you get an error instead of a slow query.

`bits4` is the default TurboQuant setting that the Qdrant docs describe as roughly 8x compression.

## Step 2: Declare the indexes

Declare an index for every field you want to filter on. Run each of these three requests separately.

```http
PUT /collections/recipes/index
{ "field_name": "cuisine", "field_schema": "keyword" }
```

```http
PUT /collections/recipes/index
{ "field_name": "minutes", "field_schema": "integer" }
```

```http
PUT /collections/recipes/index
{ "field_name": "description", "field_schema": "text" }
```

## Step 3: Load a recipe

Send the text and the model name. Qdrant embeds the text inside your cluster and stores the vector with the payload.

```http
PUT /collections/recipes/points?wait=true
{
  "points": [
    {
      "id": 1,
      "vector": {
        "text": "A quick coconut curry with crispy tofu, lime, and fresh basil.",
        "model": "<model from the Inference tab>"
      },
      "payload": {
        "title": "Green Curry with Tofu",
        "cuisine": "thai",
        "minutes": 25,
        "vegetarian": true,
        "added_on": "2026-10-03",
        "description": "A quick coconut curry with crispy tofu, lime, and fresh basil."
      }
    }
  ]
}
```

Load more recipes the same way, with a new `id` each time. Qdrant embeds each text when you load it.

## Step 4: Search with a filter

This query asks for something quick and vegetarian for dinner. Qdrant embeds the question, then keeps only Thai dishes under 30 minutes before ranking the rest.

```http
POST /collections/recipes/points/query
{
  "query": {
    "text": "something quick and vegetarian for dinner",
    "model": "<model from the Inference tab>"
  },
  "filter": {
    "must": [
      { "key": "cuisine", "match": { "value": "thai" } },
      { "key": "minutes", "range": { "lt": 30 } }
    ]
  },
  "limit": 3,
  "with_payload": true
}
```

## Step 5: Clean up

When you finish, delete the collection. This removes its vectors, payloads, and indexes.

```http
DELETE /collections/recipes
```

## Troubleshooting

- **"InferenceService URL not configured"**: Cloud Inference is not enabled for this cluster, or you are running the request on a self-hosted server. Use a Qdrant Cloud cluster.
- **A vector size error on load**: the `size` in step 1 does not match the model's vector size from the Inference tab. Delete the collection and create it again with the right size.
- **A recipe does not appear in the search**: check its payload with the filter test in [payload-schema-test.md](payload-schema-test.md). A value with the wrong type, such as `"minutes": "20"` instead of `20`, is stored but skipped by range filters.
