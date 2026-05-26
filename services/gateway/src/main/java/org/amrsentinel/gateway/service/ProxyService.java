package org.amrsentinel.gateway.service;

import com.fasterxml.jackson.databind.JsonNode;
import org.amrsentinel.gateway.auth.AuthenticatedUser;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpMethod;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Mono;

import java.util.Map;

/**
 * Forwards requests to backend services, injecting the authenticated facility_id
 * to enforce multi-tenancy.
 *
 * Returns Mono&lt;JsonNode&gt; so Spring serializes the body as JSON.
 * Returning Mono&lt;String&gt; would either send text/plain or double-encode the JSON.
 */
@Service
public class ProxyService {

    private final WebClient ingestionClient;
    private final WebClient intelligenceClient;
    private final WebClient agenticClient;

    public ProxyService(@Qualifier("ingestionClient") WebClient ingestionClient,
                        @Qualifier("intelligenceClient") WebClient intelligenceClient,
                        @Qualifier("agenticClient") WebClient agenticClient) {
        this.ingestionClient = ingestionClient;
        this.intelligenceClient = intelligenceClient;
        this.agenticClient = agenticClient;
    }

    public Mono<JsonNode> intelligenceGet(String path, Map<String, String> queryParams) {
        return intelligenceClient.get()
            .uri(uri -> {
                queryParams.forEach(uri::queryParam);
                return uri.path(path).queryParam("facility_id", currentFacility()).build();
            })
            .retrieve()
            .bodyToMono(JsonNode.class);
    }

    public Mono<JsonNode> agenticPost(String path, Object body) {
        return agenticClient.post()
            .uri(path)
            .header("X-Facility-Id", currentFacility())
            .header("X-User-Id", currentUserId())
            .body(BodyInserters.fromValue(body))
            .retrieve()
            .bodyToMono(JsonNode.class);
    }

    public Mono<JsonNode> ingestionForward(HttpMethod method, String path, Object body) {
        WebClient.RequestBodySpec spec = ingestionClient.method(method).uri(path)
            .header("X-Facility-Id", currentFacility());
        if (body != null) {
            return spec.body(BodyInserters.fromValue(body)).retrieve().bodyToMono(JsonNode.class);
        }
        return spec.retrieve().bodyToMono(JsonNode.class);
    }

    private String currentFacility() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        if (principal instanceof AuthenticatedUser u) {
            return u.facilityId();
        }
        throw new IllegalStateException("No authenticated user");
    }

    private String currentUserId() {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        if (principal instanceof AuthenticatedUser u) {
            return u.userId();
        }
        throw new IllegalStateException("No authenticated user");
    }
}
