# OCR API Response Formats Reference

Comprehensive documentation of major OCR provider API response formats. This reference enables DTAT-OCR to mimic industry-standard response structures.

**Last Updated:** 2026-01-29

---

## Table of Contents

1. [AWS Textract](#aws-textract)
   - [DetectDocumentText](#detectdocumenttext)
   - [AnalyzeDocument (Tables)](#analyzedocument-tables)
2. [Google Cloud Vision API](#google-cloud-vision-api)
   - [textAnnotations](#textannotations)
   - [fullTextAnnotation](#fulltextannotation)
3. [Azure Computer Vision](#azure-computer-vision)
   - [Read API](#read-api)
4. [Comparison Matrix](#comparison-matrix)

---

## AWS Textract

Amazon Textract provides two main operations: `DetectDocumentText` for basic text extraction and `AnalyzeDocument` for advanced features like tables and forms.

### DetectDocumentText

**Use Case:** Basic text extraction from documents (synchronous, < 10 MB)

#### Response Structure

```json
{
  "Blocks": [
    {
      "BlockType": "string",
      "Confidence": number,
      "Geometry": {
        "BoundingBox": {
          "Height": number,
          "Left": number,
          "Top": number,
          "Width": number
        },
        "Polygon": [
          {
            "X": number,
            "Y": number
          }
        ],
        "RotationAngle": number
      },
      "Id": "string",
      "Page": number,
      "Relationships": [
        {
          "Ids": ["string"],
          "Type": "string"
        }
      ],
      "Text": "string",
      "TextType": "string"
    }
  ],
  "DetectDocumentTextModelVersion": "string",
  "DocumentMetadata": {
    "Pages": number
  }
}
```

#### Complete Example

```json
{
  "Blocks": [
    {
      "BlockType": "PAGE",
      "Geometry": {
        "BoundingBox": {
          "Width": 1.0,
          "Height": 1.0,
          "Left": 0.0,
          "Top": 0.0
        },
        "Polygon": [
          {"X": 0.0, "Y": 0.0},
          {"X": 1.0, "Y": 0.0},
          {"X": 1.0, "Y": 1.0},
          {"X": 0.0, "Y": 1.0}
        ],
        "RotationAngle": 0.0
      },
      "Id": "page-1",
      "Relationships": [
        {
          "Type": "CHILD",
          "Ids": ["line-1", "line-2"]
        }
      ],
      "Confidence": 99.0,
      "Page": 1
    },
    {
      "BlockType": "LINE",
      "Text": "Hello World",
      "Confidence": 98.5,
      "Geometry": {
        "BoundingBox": {
          "Width": 0.5,
          "Height": 0.05,
          "Left": 0.1,
          "Top": 0.1
        },
        "Polygon": [
          {"X": 0.1, "Y": 0.1},
          {"X": 0.6, "Y": 0.1},
          {"X": 0.6, "Y": 0.15},
          {"X": 0.1, "Y": 0.15}
        ]
      },
      "Id": "line-1",
      "Page": 1,
      "Relationships": [
        {
          "Type": "CHILD",
          "Ids": ["word-1", "word-2"]
        }
      ]
    },
    {
      "BlockType": "WORD",
      "Text": "Hello",
      "Confidence": 99.2,
      "Geometry": {
        "BoundingBox": {
          "Width": 0.2,
          "Height": 0.05,
          "Left": 0.1,
          "Top": 0.1
        },
        "Polygon": [
          {"X": 0.1, "Y": 0.1},
          {"X": 0.3, "Y": 0.1},
          {"X": 0.3, "Y": 0.15},
          {"X": 0.1, "Y": 0.15}
        ]
      },
      "Id": "word-1",
      "Page": 1
    },
    {
      "BlockType": "WORD",
      "Text": "World",
      "Confidence": 97.8,
      "Geometry": {
        "BoundingBox": {
          "Width": 0.2,
          "Height": 0.05,
          "Left": 0.35,
          "Top": 0.1
        },
        "Polygon": [
          {"X": 0.35, "Y": 0.1},
          {"X": 0.55, "Y": 0.1},
          {"X": 0.55, "Y": 0.15},
          {"X": 0.35, "Y": 0.15}
        ]
      },
      "Id": "word-2",
      "Page": 1
    }
  ],
  "DetectDocumentTextModelVersion": "1.0",
  "DocumentMetadata": {
    "Pages": 1
  }
}
```

#### BlockType Values

| BlockType | Description | Contains Text | Has Children |
|-----------|-------------|---------------|--------------|
| `PAGE` | Document page | No | Yes (LINE blocks) |
| `LINE` | Line of text | Yes | Yes (WORD blocks) |
| `WORD` | Individual word | Yes | No |
| `TABLE` | Table structure | No | Yes (CELL blocks) |
| `CELL` | Table cell | No | Yes (WORD blocks) |
| `KEY_VALUE_SET` | Form field | No | Yes (KEY/VALUE blocks) |
| `SELECTION_ELEMENT` | Checkbox/radio button | No | No |
| `QUERY` | Query result | Yes | No |
| `LAYOUT` | Layout element | No | Yes |

#### Key Properties

- **Confidence**: Float (0-100) indicating detection confidence
- **Geometry**: Contains both `BoundingBox` (rectangular) and `Polygon` (precise) coordinates
- **BoundingBox Coordinates**: Normalized (0.0-1.0) relative to page dimensions
  - `Left`: Distance from left edge (0.0 = left edge, 1.0 = right edge)
  - `Top`: Distance from top edge (0.0 = top, 1.0 = bottom)
  - `Width`: Width as proportion of page width
  - `Height`: Height as proportion of page height
- **Polygon**: Array of 4 vertices (top-left, top-right, bottom-right, bottom-left)
- **Relationships**: Defines parent-child hierarchy
  - `CHILD`: Lists child block IDs
  - `VALUE`: Links KEY blocks to VALUE blocks
  - Relationships are directional (parent → child)

### AnalyzeDocument (Tables)

**Use Case:** Extract tables, forms, and structured data

#### TABLE Block Structure

```json
{
  "BlockType": "TABLE",
  "Confidence": 99.8046875,
  "Geometry": {
    "BoundingBox": {
      "Width": 0.9,
      "Height": 0.4,
      "Left": 0.05,
      "Top": 0.2
    },
    "Polygon": [
      {"X": 0.05, "Y": 0.2},
      {"X": 0.95, "Y": 0.2},
      {"X": 0.95, "Y": 0.6},
      {"X": 0.05, "Y": 0.6}
    ]
  },
  "Id": "table-1",
  "Page": 1,
  "Relationships": [
    {
      "Type": "CHILD",
      "Ids": [
        "cell-1", "cell-2", "cell-3", "cell-4"
      ]
    },
    {
      "Type": "MERGED_CELL",
      "Ids": ["merged-cell-1", "merged-cell-2"]
    },
    {
      "Type": "TABLE_TITLE",
      "Ids": ["title-block-1"]
    },
    {
      "Type": "TABLE_FOOTER",
      "Ids": ["footer-block-1"]
    }
  ],
  "EntityTypes": ["STRUCTURED_TABLE"]
}
```

#### CELL Block Structure

```json
{
  "BlockType": "CELL",
  "Confidence": 81.8359375,
  "RowIndex": 2,
  "ColumnIndex": 1,
  "RowSpan": 1,
  "ColumnSpan": 1,
  "Geometry": {
    "BoundingBox": {
      "Width": 0.2,
      "Height": 0.05,
      "Left": 0.1,
      "Top": 0.3
    },
    "Polygon": [
      {"X": 0.1, "Y": 0.3},
      {"X": 0.3, "Y": 0.3},
      {"X": 0.3, "Y": 0.35},
      {"X": 0.1, "Y": 0.35}
    ]
  },
  "Id": "cell-1",
  "Page": 1,
  "Relationships": [
    {
      "Type": "CHILD",
      "Ids": ["word-123"]
    }
  ],
  "EntityTypes": ["COLUMN_HEADER"]
}
```

#### MERGED_CELL Block Structure

```json
{
  "BlockType": "MERGED_CELL",
  "Confidence": 77.44140625,
  "RowIndex": 1,
  "ColumnIndex": 1,
  "RowSpan": 1,
  "ColumnSpan": 5,
  "Geometry": {
    "BoundingBox": {
      "Width": 0.8,
      "Height": 0.05,
      "Left": 0.1,
      "Top": 0.2
    },
    "Polygon": [
      {"X": 0.1, "Y": 0.2},
      {"X": 0.9, "Y": 0.2},
      {"X": 0.9, "Y": 0.25},
      {"X": 0.1, "Y": 0.25}
    ]
  },
  "Id": "merged-cell-1",
  "Page": 1,
  "Relationships": [
    {
      "Type": "CHILD",
      "Ids": ["cell-1", "cell-2", "cell-3", "cell-4", "cell-5"]
    }
  ],
  "EntityTypes": ["TABLE_TITLE"]
}
```

#### Table Cell EntityTypes

| EntityType | Description |
|------------|-------------|
| `COLUMN_HEADER` | Column header cell |
| `TABLE_TITLE` | Table title |
| `TABLE_FOOTER` | Table footer |
| `TABLE_SECTION_TITLE` | Section heading within table |
| `TABLE_SUMMARY` | Summary row in table |
| _(none)_ | Regular data cell |

#### Table Properties

- **RowIndex**: Row position (0-based indexing)
- **ColumnIndex**: Column position (0-based indexing)
- **RowSpan**: Number of rows the cell spans (usually 1)
- **ColumnSpan**: Number of columns the cell spans (> 1 for merged cells)

---

## Google Cloud Vision API

Google Cloud Vision provides two OCR annotation formats: `textAnnotations` (simple) and `fullTextAnnotation` (hierarchical).

### textAnnotations

**Use Case:** Simple text extraction with bounding boxes

#### Response Structure

```json
{
  "responses": [
    {
      "textAnnotations": [
        {
          "locale": "string",
          "description": "string",
          "boundingPoly": {
            "vertices": [
              { "x": number, "y": number }
            ]
          }
        }
      ]
    }
  ]
}
```

#### Complete Example

```json
{
  "responses": [
    {
      "textAnnotations": [
        {
          "locale": "en",
          "description": "WAITING?\nPLEASE\nTURN OFF\nYOUR\nENGINE\n",
          "boundingPoly": {
            "vertices": [
              { "x": 341, "y": 828 },
              { "x": 2249, "y": 828 },
              { "x": 2249, "y": 1993 },
              { "x": 341, "y": 1993 }
            ]
          }
        },
        {
          "description": "WAITING?",
          "boundingPoly": {
            "vertices": [
              { "x": 352, "y": 828 },
              { "x": 2248, "y": 911 },
              { "x": 2238, "y": 1148 },
              { "x": 342, "y": 1065 }
            ]
          }
        },
        {
          "description": "PLEASE",
          "boundingPoly": {
            "vertices": [
              { "x": 1210, "y": 1233 },
              { "x": 1907, "y": 1263 },
              { "x": 1902, "y": 1383 },
              { "x": 1205, "y": 1353 }
            ]
          }
        },
        {
          "description": "TURN",
          "boundingPoly": {
            "vertices": [
              { "x": 345, "y": 1388 },
              { "x": 779, "y": 1408 },
              { "x": 776, "y": 1523 },
              { "x": 342, "y": 1503 }
            ]
          }
        },
        {
          "description": "OFF",
          "boundingPoly": {
            "vertices": [
              { "x": 826, "y": 1411 },
              { "x": 1098, "y": 1423 },
              { "x": 1095, "y": 1538 },
              { "x": 823, "y": 1526 }
            ]
          }
        }
      ]
    }
  ]
}
```

#### Key Properties

- **First Element**: Always contains the entire detected text block with `locale` field
- **Subsequent Elements**: Individual words/phrases extracted from the text
- **locale**: Language code (e.g., "en", "fr", "es") - only present in first element
- **description**: Detected text content
- **boundingPoly**: Polygon vertices defining text location
- **vertices**: Array of corner coordinates (usually 4 points: top-left, top-right, bottom-right, bottom-left)
- **Coordinate System**: Absolute pixel coordinates (not normalized)
- **Missing Coordinates**: When x or y = 0, the coordinate is omitted from JSON

### fullTextAnnotation

**Use Case:** Structured document analysis with hierarchical organization

#### Hierarchy Structure

```
fullTextAnnotation
├── text (complete extracted text)
├── pages[]
    ├── property (detectedLanguages[], confidence)
    ├── width
    ├── height
    └── blocks[]
        ├── blockType
        ├── boundingBox (vertices)
        ├── property (detectedLanguages[])
        └── paragraphs[]
            ├── boundingBox (vertices)
            ├── property (detectedLanguages[])
            └── words[]
                ├── boundingBox (vertices)
                ├── property (detectedLanguages[])
                └── symbols[]
                    ├── property (detectedBreak)
                    ├── boundingBox (vertices)
                    ├── text
                    └── confidence
```

#### Conceptual Example (Partial)

```json
{
  "fullTextAnnotation": {
    "text": "Complete extracted text...",
    "pages": [
      {
        "property": {
          "detectedLanguages": [
            {
              "languageCode": "en",
              "confidence": 0.95
            }
          ]
        },
        "width": 1024,
        "height": 768,
        "blocks": [
          {
            "blockType": "TEXT",
            "boundingBox": {
              "vertices": [
                { "x": 100, "y": 50 },
                { "x": 900, "y": 50 },
                { "x": 900, "y": 200 },
                { "x": 100, "y": 200 }
              ]
            },
            "paragraphs": [
              {
                "boundingBox": {
                  "vertices": [
                    { "x": 100, "y": 50 },
                    { "x": 900, "y": 50 },
                    { "x": 900, "y": 120 },
                    { "x": 100, "y": 120 }
                  ]
                },
                "words": [
                  {
                    "boundingBox": {
                      "vertices": [
                        { "x": 100, "y": 50 },
                        { "x": 200, "y": 50 },
                        { "x": 200, "y": 80 },
                        { "x": 100, "y": 80 }
                      ]
                    },
                    "symbols": [
                      {
                        "text": "H",
                        "confidence": 0.99,
                        "boundingBox": {
                          "vertices": [
                            { "x": 100, "y": 50 },
                            { "x": 120, "y": 50 },
                            { "x": 120, "y": 80 },
                            { "x": 100, "y": 80 }
                          ]
                        }
                      },
                      {
                        "text": "e",
                        "confidence": 0.98,
                        "boundingBox": {
                          "vertices": [
                            { "x": 120, "y": 50 },
                            { "x": 140, "y": 50 },
                            { "x": 140, "y": 80 },
                            { "x": 120, "y": 80 }
                          ]
                        }
                      },
                      {
                        "text": "l",
                        "confidence": 0.97,
                        "boundingBox": {
                          "vertices": [
                            { "x": 140, "y": 50 },
                            { "x": 155, "y": 50 },
                            { "x": 155, "y": 80 },
                            { "x": 140, "y": 80 }
                          ]
                        }
                      },
                      {
                        "text": "l",
                        "confidence": 0.97,
                        "boundingBox": {
                          "vertices": [
                            { "x": 155, "y": 50 },
                            { "x": 170, "y": 50 },
                            { "x": 170, "y": 80 },
                            { "x": 155, "y": 80 }
                          ]
                        }
                      },
                      {
                        "text": "o",
                        "confidence": 0.98,
                        "boundingBox": {
                          "vertices": [
                            { "x": 170, "y": 50 },
                            { "x": 200, "y": 50 },
                            { "x": 200, "y": 80 },
                            { "x": 170, "y": 80 }
                          ]
                        },
                        "property": {
                          "detectedBreak": {
                            "type": "SPACE"
                          }
                        }
                      }
                    ]
                  }
                ]
              }
            ]
          }
        ]
      }
    ]
  }
}
```

#### detectedBreak Types

Break types indicate text formatting boundaries at the symbol level:

| Break Type | Description |
|------------|-------------|
| `SPACE` | Space between words |
| `LINE_BREAK` | End of line |
| `EOL_SURE_SPACE` | End of line with space |
| `HYPHEN` | Hyphenated word break |

#### blockType Values

| Block Type | Description |
|------------|-------------|
| `TEXT` | Text block |
| `TABLE` | Table structure |
| `PICTURE` | Image/picture |
| `RULER` | Horizontal line |
| `BARCODE` | Barcode |

#### Key Properties

- **text**: Complete extracted text (available at `fullTextAnnotation.text`)
- **confidence**: Float (0.0-1.0) at symbol level
- **detectedLanguages**: Array of language codes with confidence scores
- **boundingBox**: Present at all hierarchy levels (block, paragraph, word, symbol)
- **Coordinate System**: Absolute pixel coordinates

---

## Azure Computer Vision

Azure Computer Vision provides the Read API for comprehensive OCR with async processing.

### Read API

**Use Case:** Production OCR with handwriting support, 73 languages, async processing

#### Response Structure

```json
{
  "status": "string",
  "createdDateTime": "string",
  "lastUpdatedDateTime": "string",
  "analyzeResult": {
    "version": "string",
    "modelVersion": "string",
    "readResults": [
      {
        "page": number,
        "angle": number,
        "width": number,
        "height": number,
        "unit": "string",
        "lines": [
          {
            "boundingBox": [number],
            "text": "string",
            "appearance": {
              "style": {
                "name": "string",
                "confidence": number
              }
            },
            "words": [
              {
                "boundingBox": [number],
                "text": "string",
                "confidence": number
              }
            ]
          }
        ]
      }
    ]
  }
}
```

#### Complete Example

```json
{
  "status": "succeeded",
  "createdDateTime": "2021-02-04T06:32:08.2752706+00:00",
  "lastUpdatedDateTime": "2021-02-04T06:32:08.7706172+00:00",
  "analyzeResult": {
    "version": "3.2",
    "modelVersion": "2021-04-12",
    "readResults": [
      {
        "page": 1,
        "angle": 2.1243,
        "width": 502,
        "height": 252,
        "unit": "pixel",
        "lines": [
          {
            "boundingBox": [58, 42, 314, 59, 311, 123, 56, 121],
            "text": "Tabs vs",
            "appearance": {
              "style": {
                "name": "handwriting",
                "confidence": 0.96
              }
            },
            "words": [
              {
                "boundingBox": [68, 44, 225, 59, 224, 122, 66, 123],
                "text": "Tabs",
                "confidence": 0.933
              },
              {
                "boundingBox": [241, 61, 314, 72, 314, 123, 239, 122],
                "text": "vs",
                "confidence": 0.977
              }
            ]
          },
          {
            "boundingBox": [286, 171, 415, 165, 417, 197, 287, 201],
            "text": "Spaces",
            "appearance": {
              "style": {
                "name": "print",
                "confidence": 0.81
              }
            },
            "words": [
              {
                "boundingBox": [286, 179, 339, 175, 340, 206, 287, 207],
                "text": "Spa",
                "confidence": 0.977
              },
              {
                "boundingBox": [341, 175, 415, 165, 417, 197, 342, 206],
                "text": "ces",
                "confidence": 0.983
              }
            ]
          }
        ]
      },
      {
        "page": 2,
        "angle": 0.0,
        "width": 612,
        "height": 792,
        "unit": "pixel",
        "lines": [
          {
            "boundingBox": [100, 50, 500, 50, 500, 80, 100, 80],
            "text": "Second page content",
            "appearance": {
              "style": {
                "name": "print",
                "confidence": 0.95
              }
            },
            "words": [
              {
                "boundingBox": [100, 50, 200, 50, 200, 80, 100, 80],
                "text": "Second",
                "confidence": 0.99
              },
              {
                "boundingBox": [210, 50, 280, 50, 280, 80, 210, 80],
                "text": "page",
                "confidence": 0.98
              },
              {
                "boundingBox": [290, 50, 400, 50, 400, 80, 290, 80],
                "text": "content",
                "confidence": 0.97
              }
            ]
          }
        ]
      }
    ]
  }
}
```

#### Status Values

| Status | Description |
|--------|-------------|
| `notStarted` | Operation hasn't begun |
| `running` | Currently processing |
| `failed` | Operation failed |
| `succeeded` | Successfully completed with results available |

#### Key Properties

- **status**: Operation status (async processing)
- **analyzeResult**: Contains all OCR results (only present when status = "succeeded")
- **version**: API version (e.g., "3.2")
- **modelVersion**: AI model version used (e.g., "2021-04-12")
- **readResults**: Array of results per page
- **page**: Page number (1-indexed)
- **angle**: Detected rotation angle in degrees
- **width/height**: Image dimensions in pixels
- **unit**: Measurement unit (always "pixel")
- **boundingBox**: 8-value array `[x1, y1, x2, y2, x3, y3, x4, y4]` representing 4 corner coordinates
  - Order: top-left, top-right, bottom-right, bottom-left
- **text**: Extracted text content
- **confidence**: Confidence score (0.0-1.0) for each word
- **appearance.style**: Text style classification
  - `name`: "handwriting" or "print"
  - `confidence`: Style classification confidence (0.0-1.0)
  - Only available for Latin languages
- **Coordinate System**: Absolute pixel coordinates

#### Important Notes

- **Async Processing**: Read API uses submit-then-poll pattern
  1. POST to `/vision/v3.2/read/analyze` returns Operation-Location header
  2. GET Operation-Location URL to check status
  3. Poll until status = "succeeded" or "failed"
- **Language Detection**: Read API does NOT auto-detect language
  - Must specify language in request parameter
  - No language field in response
  - Supports 73 languages
- **No Language Field**: Unlike other providers, Azure doesn't return detected language in response

---

## Comparison Matrix

### Core Features

| Feature | AWS Textract | Google Cloud Vision | Azure Computer Vision |
|---------|--------------|---------------------|----------------------|
| **Basic OCR** | DetectDocumentText | TEXT_DETECTION | Read API |
| **Advanced OCR** | AnalyzeDocument | DOCUMENT_TEXT_DETECTION | Read API |
| **Processing** | Sync (< 10 MB) or Async | Sync | Async only |
| **Max File Size** | 10 MB (sync), 500 MB (async) | 75 MB | 50 MB |
| **Tables** | Yes (AnalyzeDocument) | Limited | No |
| **Forms** | Yes (AnalyzeDocument) | Limited | No |
| **Handwriting** | Yes | Yes | Yes |

### Response Structure Differences

| Aspect | AWS Textract | Google Cloud Vision | Azure Computer Vision |
|--------|--------------|---------------------|----------------------|
| **Hierarchy** | PAGE → LINE → WORD | Page → Block → Paragraph → Word → Symbol | Page → Line → Word |
| **Coordinates** | Normalized (0.0-1.0) | Absolute pixels | Absolute pixels |
| **Bounding Shape** | Both Box & Polygon | Polygon only | 8-point polygon |
| **Confidence** | 0-100 (percent) | 0.0-1.0 (decimal) | 0.0-1.0 (decimal) |
| **Language Detection** | No | Yes (automatic) | No (must specify) |
| **Relationships** | Explicit parent-child | Implicit hierarchy | Implicit hierarchy |

### Coordinate Systems

#### AWS Textract (Normalized)
```json
{
  "BoundingBox": {
    "Left": 0.1,    // 10% from left edge
    "Top": 0.2,     // 20% from top edge
    "Width": 0.3,   // 30% of page width
    "Height": 0.05  // 5% of page height
  }
}
```

**Advantages:**
- Resolution-independent
- Easy to scale to different display sizes
- Consistent across documents

**Disadvantages:**
- Requires page dimensions to get absolute coordinates

#### Google Cloud Vision (Absolute Pixels)
```json
{
  "vertices": [
    { "x": 100, "y": 50 },   // Top-left corner
    { "x": 400, "y": 50 },   // Top-right corner
    { "x": 400, "y": 100 },  // Bottom-right corner
    { "x": 100, "y": 100 }   // Bottom-left corner
  ]
}
```

**Advantages:**
- Direct pixel coordinates
- No conversion needed
- Handles rotated text (4-point polygon)

**Disadvantages:**
- Resolution-dependent
- Must scale when resizing

#### Azure Computer Vision (8-Point Array)
```json
{
  "boundingBox": [100, 50, 400, 50, 400, 100, 100, 100]
}
```

Format: `[x1, y1, x2, y2, x3, y3, x4, y4]`
- (x1, y1) = top-left
- (x2, y2) = top-right
- (x3, y3) = bottom-right
- (x4, y4) = bottom-left

**Advantages:**
- Compact representation
- Handles rotated text

**Disadvantages:**
- Less intuitive than object format
- Must parse array in order

### Confidence Scoring

| Provider | Range | Format | Example |
|----------|-------|--------|---------|
| AWS Textract | 0-100 | Percentage | `"Confidence": 98.5` |
| Google Cloud Vision | 0.0-1.0 | Decimal | `"confidence": 0.985` |
| Azure Computer Vision | 0.0-1.0 | Decimal | `"confidence": 0.985` |

**Conversion:**
- AWS to Google/Azure: `confidence = aws_confidence / 100`
- Google/Azure to AWS: `confidence = google_confidence * 100`

### Error Handling

#### AWS Textract
```json
{
  "Error": {
    "Code": "InvalidParameterException",
    "Message": "Request has invalid image format"
  }
}
```

#### Google Cloud Vision
```json
{
  "responses": [
    {
      "error": {
        "code": 3,
        "message": "Image processing failed",
        "status": "INVALID_ARGUMENT"
      }
    }
  ]
}
```

#### Azure Computer Vision
```json
{
  "status": "failed",
  "createdDateTime": "2021-02-04T06:32:08Z",
  "lastUpdatedDateTime": "2021-02-04T06:32:10Z",
  "error": {
    "code": "InvalidImageFormat",
    "message": "The image format is not supported."
  }
}
```

---

## Implementation Notes for DTAT-OCR

### Format Conversion Strategy

1. **Internal Format**: Use AWS Textract-style normalized coordinates
   - Advantages: Resolution-independent, scale-friendly
   - Store in SQLite as JSON

2. **API Output**: Provide configurable response format
   - Default: AWS Textract format
   - Optional: Google Cloud Vision format
   - Optional: Azure format
   - Use query parameter: `?format=textract|google|azure`

3. **Coordinate Conversion**:
```python
# Normalized to absolute
def normalized_to_absolute(bbox, page_width, page_height):
    return {
        "x": bbox["Left"] * page_width,
        "y": bbox["Top"] * page_height,
        "width": bbox["Width"] * page_width,
        "height": bbox["Height"] * page_height
    }

# Absolute to normalized
def absolute_to_normalized(bbox, page_width, page_height):
    return {
        "Left": bbox["x"] / page_width,
        "Top": bbox["y"] / page_height,
        "Width": bbox["width"] / page_width,
        "Height": bbox["height"] / page_height
    }

# To Google Cloud Vision format
def to_google_format(textract_blocks, page_width, page_height):
    annotations = []
    for block in textract_blocks:
        if block["BlockType"] == "WORD":
            bbox = block["Geometry"]["BoundingBox"]
            x = bbox["Left"] * page_width
            y = bbox["Top"] * page_height
            w = bbox["Width"] * page_width
            h = bbox["Height"] * page_height

            annotations.append({
                "description": block["Text"],
                "boundingPoly": {
                    "vertices": [
                        {"x": int(x), "y": int(y)},
                        {"x": int(x + w), "y": int(y)},
                        {"x": int(x + w), "y": int(y + h)},
                        {"x": int(x), "y": int(y + h)}
                    ]
                }
            })

    return {"responses": [{"textAnnotations": annotations}]}

# To Azure format
def to_azure_format(textract_blocks, page_width, page_height):
    lines = []
    current_line = None

    for block in textract_blocks:
        if block["BlockType"] == "LINE":
            bbox = block["Geometry"]["BoundingBox"]
            x = bbox["Left"] * page_width
            y = bbox["Top"] * page_height
            w = bbox["Width"] * page_width
            h = bbox["Height"] * page_height

            line = {
                "boundingBox": [
                    int(x), int(y),
                    int(x + w), int(y),
                    int(x + w), int(y + h),
                    int(x), int(y + h)
                ],
                "text": block["Text"],
                "words": []
            }

            # Add words (from CHILD relationship)
            if "Relationships" in block:
                for rel in block["Relationships"]:
                    if rel["Type"] == "CHILD":
                        for word_id in rel["Ids"]:
                            word_block = find_block_by_id(word_id, textract_blocks)
                            if word_block:
                                word_bbox = word_block["Geometry"]["BoundingBox"]
                                wx = word_bbox["Left"] * page_width
                                wy = word_bbox["Top"] * page_height
                                ww = word_bbox["Width"] * page_width
                                wh = word_bbox["Height"] * page_height

                                line["words"].append({
                                    "boundingBox": [
                                        int(wx), int(wy),
                                        int(wx + ww), int(wy),
                                        int(wx + ww), int(wy + wh),
                                        int(wx), int(wy + wh)
                                    ],
                                    "text": word_block["Text"],
                                    "confidence": word_block["Confidence"] / 100
                                })

            lines.append(line)

    return {
        "status": "succeeded",
        "analyzeResult": {
            "version": "3.2",
            "readResults": [{
                "page": 1,
                "angle": 0.0,
                "width": page_width,
                "height": page_height,
                "unit": "pixel",
                "lines": lines
            }]
        }
    }
```

### Confidence Score Mapping

DTAT-OCR quality scores (0-100) map directly to AWS Textract format. For other providers:

```python
def convert_confidence(score, source_format="dtat", target_format="textract"):
    # DTAT and Textract use 0-100
    # Google and Azure use 0.0-1.0

    if source_format in ["dtat", "textract"]:
        if target_format in ["google", "azure"]:
            return score / 100
        return score

    if source_format in ["google", "azure"]:
        if target_format in ["dtat", "textract"]:
            return score * 100
        return score
```

### Language Detection

DTAT-OCR should:
1. Use `langdetect` or `lingua` for language detection
2. Return language in Google Cloud Vision format (for compatibility)
3. Make it optional (like Azure)

```python
from langdetect import detect

def detect_language(text):
    try:
        lang_code = detect(text)
        return {
            "locale": lang_code,  # Google format
            "confidence": 0.95    # Estimated
        }
    except:
        return None
```

---

## Sources

### AWS Textract
- [DetectDocumentText API Documentation](https://docs.aws.amazon.com/textract/latest/dg/API_DetectDocumentText.html)
- [Text Detection and Document Analysis Response Objects](https://docs.aws.amazon.com/textract/latest/dg/how-it-works-document-layout.html)
- [Amazon Textract Tables Documentation](https://docs.aws.amazon.com/textract/latest/dg/how-it-works-tables.html)
- [AnalyzeDocument API Documentation](https://docs.aws.amazon.com/textract/latest/dg/API_AnalyzeDocument.html)
- [Amazon Textract Response Parser (GitHub)](https://github.com/aws-samples/amazon-textract-response-parser)

### Google Cloud Vision API
- [Detect text in images Documentation](https://docs.cloud.google.com/vision/docs/ocr)
- [Dense document text detection tutorial](https://cloud.google.com/vision/docs/fulltext-annotations)
- [Google Cloud Vision API Examples (GitHub)](https://github.com/GoogleCloudPlatform/cloud-vision)
- [Cloud Vision Python Text README](https://github.com/GoogleCloudPlatform/cloud-vision/blob/master/python/text/README.md)
- [Cloud Vision DetectedBreak Issue (GitHub)](https://github.com/googleapis/google-cloud-dotnet/issues/6783)

### Azure Computer Vision
- [Call Azure Vision Read API Documentation](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/how-to/call-read-api)
- [OCR for images - Azure Vision in Foundry Tools](https://learn.microsoft.com/en-us/azure/ai-services/computer-vision/concept-ocr)
- [Read API REST Reference](https://learn.microsoft.com/en-us/rest/api/computervision/read/read?view=rest-computervision-v3.1)
- [Computer Vision Read OCR API Announcement](https://techcommunity.microsoft.com/blog/azure-ai-foundry-blog/computer-vision-read-ocr-api-previews-73-human-languages-and-new-features-on-clo/2121341)

---

**Document Version:** 1.0
**Created:** 2026-01-29
**Last Updated:** 2026-01-29
