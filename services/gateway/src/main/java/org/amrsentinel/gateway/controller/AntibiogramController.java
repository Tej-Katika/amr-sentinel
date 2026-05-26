package org.amrsentinel.gateway.controller;

import com.fasterxml.jackson.databind.JsonNode;
import org.amrsentinel.gateway.service.ProxyService;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import reactor.core.publisher.Mono;

import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/antibiogram")
public class AntibiogramController {

    private final ProxyService proxyService;

    public AntibiogramController(ProxyService proxyService) {
        this.proxyService = proxyService;
    }

    @GetMapping
    public Mono<JsonNode> get(@RequestParam(required = false) String organism,
                              @RequestParam(required = false, defaultValue = "12") Integer periodMonths,
                              @RequestParam(required = false, defaultValue = "ALL") String stratification) {
        Map<String, String> params = new HashMap<>();
        if (organism != null) params.put("organism", organism);
        params.put("period_months", String.valueOf(periodMonths));
        params.put("stratification", stratification);
        return proxyService.intelligenceGet("/antibiogram", params);
    }
}
