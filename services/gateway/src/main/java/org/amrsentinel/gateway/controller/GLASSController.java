package org.amrsentinel.gateway.controller;

import org.amrsentinel.gateway.auth.AuthenticatedUser;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.core.publisher.Flux;

@RestController
@RequestMapping("/api/glass")
public class GLASSController {

    private final WebClient intelligenceClient;

    public GLASSController(@Qualifier("intelligenceClient") WebClient intelligenceClient) {
        this.intelligenceClient = intelligenceClient;
    }

    @GetMapping("/ris.csv")
    public Flux<DataBuffer> ris(@RequestParam int year) {
        return passthrough("/glass/ris.csv", year);
    }

    @GetMapping("/sample.csv")
    public Flux<DataBuffer> sample(@RequestParam int year) {
        return passthrough("/glass/sample.csv", year);
    }

    private Flux<DataBuffer> passthrough(String path, int year) {
        Object principal = SecurityContextHolder.getContext().getAuthentication().getPrincipal();
        String facilityId = ((AuthenticatedUser) principal).facilityId();
        return intelligenceClient.get()
            .uri(uri -> uri.path(path)
                .queryParam("facility_id", facilityId)
                .queryParam("year", year)
                .build())
            .retrieve()
            .bodyToFlux(DataBuffer.class);
    }
}
