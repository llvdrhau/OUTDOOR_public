


# Let's assume you have two lists of probabilities
prob_list1 = [0.1, 0.8, 0.1]  # probabilities from the first list
prob_list2 = [0.25, 0.5, 0.25]  # probabilities from the second list

# Creating a 3x3 matrix to store the probabilities of each pair
combined_prob_matrix = [[0]*3 for _ in range(3)]
print(combined_prob_matrix)

# Calculating the combined probabilities
for i in range(3):
    for j in range(3):
        combined_prob_matrix[i][j] = prob_list1[i] * prob_list2[j]
print(combined_prob_matrix)
# combined_prob_matrix now contains the probabilities of each combination
