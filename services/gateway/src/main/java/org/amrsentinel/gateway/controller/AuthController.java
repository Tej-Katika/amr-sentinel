package org.amrsentinel.gateway.controller;

import org.amrsentinel.gateway.auth.JwtTokenProvider;
import org.amrsentinel.gateway.model.User;
import org.amrsentinel.gateway.repository.UserRepository;
import org.springframework.http.ResponseEntity;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/auth")
public class AuthController {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;

    public AuthController(UserRepository userRepository,
                          PasswordEncoder passwordEncoder,
                          JwtTokenProvider jwtTokenProvider) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.jwtTokenProvider = jwtTokenProvider;
    }

    public record LoginRequest(String email, String password) {}

    @PostMapping("/login")
    public ResponseEntity<?> login(@RequestBody LoginRequest req) {
        return userRepository.findByEmail(req.email())
            .filter(u -> passwordEncoder.matches(req.password(), u.getPasswordHash()))
            .map(this::tokenResponse)
            .orElse(ResponseEntity.status(401).body(Map.of("error", "Invalid credentials")));
    }

    private ResponseEntity<Map<String, Object>> tokenResponse(User u) {
        String token = jwtTokenProvider.createToken(
            u.getUserId().toString(),
            u.getEmail(),
            u.getFacilityId(),
            u.getRole()
        );
        return ResponseEntity.ok(Map.of(
            "token", token,
            "user", Map.of(
                "user_id", u.getUserId().toString(),
                "email", u.getEmail(),
                "facility_id", u.getFacilityId(),
                "role", u.getRole(),
                "name", u.getName()
            )
        ));
    }
}
