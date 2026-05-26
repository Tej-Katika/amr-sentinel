package org.amrsentinel.gateway.controller;

import com.fasterxml.jackson.databind.JsonNode;
import org.amrsentinel.gateway.service.ProxyService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.util.Map;

@RestController
@RequestMapping("/api/agent")
public class AgentController {

    private final ProxyService proxyService;

    public AgentController(ProxyService proxyService) {
        this.proxyService = proxyService;
    }

    public record QueryRequest(String query) {}

    @PostMapping("/query")
    public Mono<JsonNode> query(@RequestBody QueryRequest req) {
        return proxyService.agenticPost("/query", Map.of("query", req.query()));
    }
}
