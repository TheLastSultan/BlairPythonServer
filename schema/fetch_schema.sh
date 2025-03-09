#!/bin/bash

# Configuration
HASURA_ENDPOINT="https://talent1.app/hasura/v1/graphql"

# Load environment variables from .env file
if [ -f "../.env" ]; then
  export $(grep -v '^#' "../.env" | xargs)
fi

# Check if ADMIN_SECRET is set
if [ -z "$ADMIN_SECRET" ]; then
  echo "Error: ADMIN_SECRET environment variable is not set."
  exit 1
fi

OUTPUT_FILE="schema.graphql"

# GraphQL introspection query to get the schema in SDL format
QUERY='
{
  __schema {
    types {
      kind
      name
      description
      fields {
        name
        description
        args {
          name
          description
          type {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
                ofType {
                  kind
                  name
                }
              }
            }
          }
          defaultValue
        }
        type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
      }
      inputFields {
        name
        description
        type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
        defaultValue
      }
      interfaces {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
            }
          }
        }
      }
      enumValues {
        name
        description
      }
      possibleTypes {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
            }
          }
        }
      }
    }
    queryType {
      name
    }
    mutationType {
      name
    }
    subscriptionType {
      name
    }
    directives {
      name
      description
      locations
      args {
        name
        description
        type {
          kind
          name
          ofType {
            kind
            name
            ofType {
              kind
              name
              ofType {
                kind
                name
              }
            }
          }
        }
        defaultValue
      }
    }
  }
}
'

# Make the introspection query
echo "Fetching GraphQL schema from $HASURA_ENDPOINT..."
curl -s -X POST "$HASURA_ENDPOINT" \
  -H "Content-Type: application/json" \
  -H "x-hasura-admin-secret: $ADMIN_SECRET" \
  -d "{\"query\": \"$(echo $QUERY | tr '\n' ' ' | sed 's/"/\\"/g')\"}" \
  -o schema_introspection.json

# Check if the curl command was successful
if [ $? -ne 0 ]; then
  echo "Error: Failed to fetch the schema."
  exit 1
fi

# Create a Node.js script to convert introspection to SDL
cat > convert_schema.js << 'EOF'
const fs = require('fs');

// Read the introspection JSON file
const introspectionData = JSON.parse(fs.readFileSync('schema_introspection.json', 'utf8'));

// Function to convert kind/name/ofType pattern to a GraphQL type string
function printType(type, isInput = false) {
  if (!type) return 'UNKNOWN_TYPE';
  
  if (type.kind === 'NON_NULL') {
    return `${printType(type.ofType, isInput)}!`;
  }
  
  if (type.kind === 'LIST') {
    return `[${printType(type.ofType, isInput)}]`;
  }
  
  return type.name;
}

// Generate SDL for a GraphQL type
function generateTypeSDL(type) {
  if (!type || !type.name) return '';
  if (type.name.startsWith('__')) return ''; // Skip internal types
  
  let sdl = '';
  
  // Add description if available
  if (type.description) {
    sdl += `"""
${type.description}
"""
`;
  }
  
  // Type definition
  if (type.kind === 'SCALAR') {
    sdl += `scalar ${type.name}`;
  } else if (type.kind === 'OBJECT') {
    sdl += `type ${type.name}`;
    
    // Add interfaces if any
    if (type.interfaces && type.interfaces.length > 0) {
      sdl += ` implements ${type.interfaces.map(i => i.name).join(' & ')}`;
    }
    
    sdl += ' {';
    
    // Add fields
    if (type.fields && type.fields.length > 0) {
      type.fields.forEach(field => {
        if (field.description) {
          sdl += `
  """
  ${field.description}
  """`;
        }
        
        // Field with arguments
        sdl += `
  ${field.name}`;
        
        // Add arguments if any
        if (field.args && field.args.length > 0) {
          sdl += `(`;
          field.args.forEach((arg, i) => {
            if (i > 0) sdl += ', ';
            sdl += `${arg.name}: ${printType(arg.type)}`;
            if (arg.defaultValue !== null && arg.defaultValue !== undefined) {
              sdl += ` = ${arg.defaultValue}`;
            }
          });
          sdl += `)`;
        }
        
        sdl += `: ${printType(field.type)}`;
      });
    }
    
    sdl += `
}`;
  } else if (type.kind === 'INTERFACE') {
    sdl += `interface ${type.name} {`;
    
    // Add fields
    if (type.fields && type.fields.length > 0) {
      type.fields.forEach(field => {
        if (field.description) {
          sdl += `
  """
  ${field.description}
  """`;
        }
        
        sdl += `
  ${field.name}`;
        
        // Add arguments if any
        if (field.args && field.args.length > 0) {
          sdl += `(`;
          field.args.forEach((arg, i) => {
            if (i > 0) sdl += ', ';
            sdl += `${arg.name}: ${printType(arg.type)}`;
            if (arg.defaultValue !== null && arg.defaultValue !== undefined) {
              sdl += ` = ${arg.defaultValue}`;
            }
          });
          sdl += `)`;
        }
        
        sdl += `: ${printType(field.type)}`;
      });
    }
    
    sdl += `
}`;
  } else if (type.kind === 'UNION') {
    sdl += `union ${type.name} = `;
    
    if (type.possibleTypes && type.possibleTypes.length > 0) {
      sdl += type.possibleTypes.map(t => t.name).join(' | ');
    }
  } else if (type.kind === 'ENUM') {
    sdl += `enum ${type.name} {`;
    
    if (type.enumValues && type.enumValues.length > 0) {
      type.enumValues.forEach(value => {
        if (value.description) {
          sdl += `
  """
  ${value.description}
  """`;
        }
        
        sdl += `
  ${value.name}`;
      });
    }
    
    sdl += `
}`;
  } else if (type.kind === 'INPUT_OBJECT') {
    sdl += `input ${type.name} {`;
    
    if (type.inputFields && type.inputFields.length > 0) {
      type.inputFields.forEach(field => {
        if (field.description) {
          sdl += `
  """
  ${field.description}
  """`;
        }
        
        sdl += `
  ${field.name}: ${printType(field.type, true)}`;
        
        if (field.defaultValue !== null && field.defaultValue !== undefined) {
          sdl += ` = ${field.defaultValue}`;
        }
      });
    }
    
    sdl += `
}`;
  }
  
  return sdl;
}

// Process the schema
function processSchema(schema) {
  let sdl = '';
  
  // Add schema definition
  sdl += `schema {`;
  
  if (schema.queryType) {
    sdl += `
  query: ${schema.queryType.name}`;
  }
  
  if (schema.mutationType) {
    sdl += `
  mutation: ${schema.mutationType.name}`;
  }
  
  if (schema.subscriptionType) {
    sdl += `
  subscription: ${schema.subscriptionType.name}`;
  }
  
  sdl += `
}

`;
  
  // Process all types
  if (schema.types && schema.types.length > 0) {
    // Sort types by kind and name for readability
    const sortedTypes = [...schema.types].sort((a, b) => {
      // First by kind
      const kindOrder = { SCALAR: 1, ENUM: 2, INTERFACE: 3, UNION: 4, OBJECT: 5, INPUT_OBJECT: 6 };
      const kindDiff = (kindOrder[a.kind] || 99) - (kindOrder[b.kind] || 99);
      if (kindDiff !== 0) return kindDiff;
      
      // Then by name
      return a.name.localeCompare(b.name);
    });
    
    sortedTypes.forEach(type => {
      const typeSDL = generateTypeSDL(type);
      if (typeSDL) {
        sdl += typeSDL + '\n\n';
      }
    });
  }
  
  // Process directives
  if (schema.directives && schema.directives.length > 0) {
    schema.directives.forEach(directive => {
      // Skip internal directives
      if (directive.name.startsWith('__')) return;
      
      if (directive.description) {
        sdl += `"""
${directive.description}
"""
`;
      }
      
      sdl += `directive @${directive.name}`;
      
      // Add arguments if any
      if (directive.args && directive.args.length > 0) {
        sdl += `(`;
        directive.args.forEach((arg, i) => {
          if (i > 0) sdl += ', ';
          sdl += `${arg.name}: ${printType(arg.type)}`;
          if (arg.defaultValue !== null && arg.defaultValue !== undefined) {
            sdl += ` = ${arg.defaultValue}`;
          }
        });
        sdl += `)`;
      }
      
      // Add locations
      if (directive.locations && directive.locations.length > 0) {
        sdl += ` on ${directive.locations.join(' | ')}`;
      }
      
      sdl += '\n\n';
    });
  }
  
  return sdl;
}

try {
  // Check if the introspection data is valid
  if (!introspectionData.data || !introspectionData.data.__schema) {
    console.error('Invalid introspection data format');
    process.exit(1);
  }
  
  // Generate SDL from the introspection data
  const sdl = processSchema(introspectionData.data.__schema);
  
  // Write the SDL to a file
  fs.writeFileSync('schema.graphql', sdl);
  console.log('SDL generated successfully');
} catch (error) {
  console.error('Error processing schema:', error);
  process.exit(1);
}
EOF

# Run the Node.js script to convert the schema
echo "Converting introspection query result to SDL format using Node.js..."
node convert_schema.js

# Check if we have a non-empty output file
if [ ! -s "$OUTPUT_FILE" ]; then
  echo "Error: Failed to convert schema to SDL format."
  exit 1
fi

# Clean up temporary files
rm -f schema_introspection.json convert_schema.js

echo "GraphQL schema successfully retrieved and saved to $OUTPUT_FILE"
echo "Number of lines in schema: $(wc -l < $OUTPUT_FILE)"