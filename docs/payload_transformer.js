// Payload transformer to fix frontend compatibility issues
// Add this BEFORE sending the request to the server

function transformPayloadForServer(frontendPayload) {
    console.log("🔧 Transforming frontend payload for server compatibility");
    console.log("📥 Input payload:", frontendPayload);

    // Create server-compatible payload
    const serverPayload = {
        company_id: frontendPayload.company_id,
        message: frontendPayload.message,

        // Fix industry format: UPPERCASE -> lowercase
        industry: frontendPayload.industry ? frontendPayload.industry.toLowerCase() : "other",

        // Fix language format: ENGLISH -> en, VIETNAMESE -> vi
        language: transformLanguage(frontendPayload.language),

        // Transform user_info structure
        user_info: transformUserInfo(frontendPayload.user_info),

        // Session ID (keep as is)
        session_id: frontendPayload.session_id,

        // Transform context structure
        context: transformContext(frontendPayload.context),

        // Transform metadata structure  
        metadata: transformMetadata(frontendPayload.metadata)
    };

    // Remove any undefined/null values
    Object.keys(serverPayload).forEach(key => {
        if (serverPayload[key] === undefined || serverPayload[key] === null) {
            delete serverPayload[key];
        }
    });

    console.log("📤 Transformed payload:", JSON.stringify(serverPayload, null, 2));
    return serverPayload;
}

function transformLanguage(frontendLang) {
    const langMap = {
        'ENGLISH': 'en',
        'VIETNAMESE': 'vi',
        'AUTO': 'auto',
        'en': 'en',
        'vi': 'vi',
        'auto': 'auto'
    };

    return langMap[frontendLang] || 'auto';
}

function transformUserInfo(frontendUserInfo) {
    if (!frontendUserInfo) return null;

    return {
        user_id: frontendUserInfo.user_id,
        source: frontendUserInfo.source || "web_device", // Ensure source is always set
        name: frontendUserInfo.name,
        email: frontendUserInfo.email,
        device_id: frontendUserInfo.device_id,
        // Transform platform_specific_data if it exists
        platform_specific_data: frontendUserInfo.platform_specific_data || null
    };
}

function transformContext(frontendContext) {
    if (!frontendContext) return null;

    // Handle nested context_data structure
    const contextData = frontendContext.context_data || frontendContext;

    return {
        page_url: contextData.page_url,
        referrer: contextData.referrer,
        timestamp: new Date().toISOString(),
        session_duration: contextData.session_duration_minutes ? contextData.session_duration_minutes * 60 : null,
        previous_intent: contextData.previous_intent || null
    };
}

function transformMetadata(frontendMetadata) {
    if (!frontendMetadata) return null;

    return {
        source: frontendMetadata.app_source || "website",
        version: frontendMetadata.app_version || "1.0.0",
        request_id: frontendMetadata.request_id,
        correlation_id: frontendMetadata.correlation_id || null
    };
}

// Usage in your existing code:
// Replace your current fetch call with this:

function sendTransformedPayload(originalPayload) {
    // Transform the payload
    const serverCompatiblePayload = transformPayloadForServer(originalPayload);

    console.log("✅ Final payload for server:", JSON.stringify(serverCompatiblePayload, null, 2));

    // Send to server
    return fetch('https://ai.aimoney.io.vn/api/unified/chat-stream', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(serverCompatiblePayload)
    })
        .then(response => {
            console.log("📡 Response status:", response.status);
            if (!response.ok) {
                console.error("❌ HTTP Error:", response.status, response.statusText);
                return response.text().then(text => {
                    console.error("❌ Error details:", text);
                    throw new Error(`HTTP error! status: ${response.status}`);
                });
            }
            console.log("✅ Request successful!");
            return response;
        })
        .catch(error => {
            console.error("💥 Request failed:", error);
            throw error;
        });
}

// Example usage with your current payload:
/*
const yourCurrentPayload = {
    company_id: "9a974d00-1a4b-4d5d-8dc3-4b5058255b8f",
    industry: "INSURANCE", // Will be transformed to "insurance"
    language: "ENGLISH",   // Will be transformed to "en"
    message: "cho tao thông tin về AIA xem",
    user_info: {
        user_id: "2Fi60Cy2jHcMhkn5o2VcjfUef7p2",
        source: "web_device",
        name: "Michael Le",
        email: "tienhoi.lh@gmail.com",
        device_id: "web_eczqgo"
    },
    // ... rest of your payload
};

// Use the transformer
sendTransformedPayload(yourCurrentPayload);
*/
